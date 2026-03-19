"""Janitor Agent — orchestrates all maintenance tasks.

Coordinates retirement evaluation, database maintenance, health checks,
state repair, log rotation, and report generation into a single run cycle.
"""

import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from absl import logging

from services.janitor_agent.dashboard import DashboardProvider
from services.janitor_agent.db_maintenance import (
    InfluxDBMaintenance,
    MaintenanceConfig,
    PostgreSQLMaintenance,
)
from services.janitor_agent.health_checker import HealthCheckConfig, HealthChecker
from services.janitor_agent.log_rotator import LogRotationConfig, LogRotator
from services.janitor_agent.notifier import (
    NotificationConfig,
    ReportDistributionConfig,
    ReportDistributor,
    RetirementNotifier,
)
from services.janitor_agent.report import JanitorReport
from services.janitor_agent.retirement_criteria import (
    Implementation,
    RetirementConfig,
    RetirementDecision,
    Spec,
    apply_batch_limits,
    can_reactivate,
    evaluate_implementation,
    evaluate_spec,
)
from services.janitor_agent.state_repair import StateRepairer


@dataclass
class JanitorConfig:
    """Combined configuration for the Janitor Agent."""

    retirement: RetirementConfig
    maintenance: MaintenanceConfig
    health_check: HealthCheckConfig
    notification: NotificationConfig = None
    report_distribution: ReportDistributionConfig = None
    log_rotation: LogRotationConfig = None

    def __post_init__(self):
        if self.notification is None:
            self.notification = NotificationConfig()
        if self.report_distribution is None:
            self.report_distribution = ReportDistributionConfig()
        if self.log_rotation is None:
            self.log_rotation = LogRotationConfig()


class JanitorAgent:
    """Main janitor agent that orchestrates all maintenance tasks."""

    def __init__(self, config: JanitorConfig):
        self._config = config
        self._pg = PostgreSQLMaintenance(config.maintenance.pg_connection_string)
        self._health = HealthChecker(config.health_check)
        self._repairer = StateRepairer(config.maintenance.pg_connection_string)
        self._notifier = RetirementNotifier(config.notification)
        self._distributor = ReportDistributor(config.report_distribution)
        self._log_rotator = LogRotator(config.log_rotation)
        self._dashboard = DashboardProvider(config.maintenance.pg_connection_string)
        self._influx: Optional[InfluxDBMaintenance] = None

        if config.maintenance.influx_url and config.maintenance.influx_token:
            self._influx = InfluxDBMaintenance(
                url=config.maintenance.influx_url,
                token=config.maintenance.influx_token,
                org=config.maintenance.influx_org,
            )

    def run_retirement_cycle(self) -> dict:
        """Evaluate and retire underperforming strategies.

        Returns a dict with retirement results for the report.
        """
        config = self._config.retirement
        logging.info("Starting retirement evaluation cycle")

        # Fetch candidates
        candidates_raw = self._pg.get_retirement_candidates(config)
        logging.info("Found %d retirement candidates", len(candidates_raw))

        decisions = []
        protected = []
        deferred = []

        for row in candidates_raw:
            # Build Implementation object
            impl = Implementation(
                impl_id=str(row["impl_id"]),
                spec_id=str(row["spec_id"]),
                symbol=row["symbol"],
                status=row["status"],
                forward_sharpe=float(row["forward_sharpe"] or 0),
                forward_accuracy=float(row["forward_accuracy"] or 0),
                forward_trades=int(row["forward_trades"] or 0),
                created_at=row["created_at"],
                updated_at=row.get("updated_at"),
                spec_source=row.get("source", ""),
                spec_name=row.get("spec_name", ""),
                preferred_regime=row.get("preferred_regime"),
            )

            # Get Sharpe trend
            impl.sharpe_trend = self._pg.get_sharpe_trend(impl.impl_id)

            # Check for better alternatives
            better_exists = self._pg.check_better_alternatives(
                impl.spec_id, impl.symbol, config.min_alternative_sharpe
            )

            # Detect current market regime for this symbol
            current_regime = self._pg.detect_market_regime(impl.symbol)

            # Evaluate
            decision = evaluate_implementation(
                impl, config, better_exists, current_regime=current_regime
            )

            if decision.reason.startswith("CANONICAL"):
                protected.append(decision)
            elif decision.reason.startswith("Deferring"):
                deferred.append(decision)
            else:
                decisions.append(decision)

        # Apply batch limits
        total_active = self._pg.get_active_implementation_count()
        to_retire = [d for d in decisions if d.should_retire]
        approved, skipped = apply_batch_limits(to_retire, total_active, config)

        # Execute retirements and notify dependent systems
        executed = []
        for decision in approved:
            result = self._pg.execute_retirement(
                decision.impl_id,
                decision.reason,
                f"Janitor Agent automated retirement: {decision.reason}",
            )
            if result.success:
                executed.append(decision)
                try:
                    self._notifier.notify_retirement(
                        impl_id=decision.impl_id,
                        spec_id=decision.spec_id,
                        symbol="",
                        reason=decision.reason,
                        metadata={
                            "final_sharpe": decision.final_sharpe,
                            "final_accuracy": decision.final_accuracy,
                            "age_days": decision.age_days,
                            "signal_count": decision.signal_count,
                        },
                    )
                except Exception as e:
                    logging.error(
                        "Failed to send notifications for %s: %s",
                        decision.impl_id,
                        e,
                    )

        # Check if any specs should be retired
        retired_specs = []
        spec_ids_to_check = set(d.spec_id for d in executed)
        for spec_id in spec_ids_to_check:
            spec_result = self._check_and_retire_spec(spec_id)
            if spec_result:
                retired_specs.append(spec_result)

        logging.info(
            "Retirement cycle complete: evaluated=%d, retired=%d, specs_retired=%d, protected=%d",
            len(candidates_raw),
            len(executed),
            len(retired_specs),
            len(protected),
        )

        return {
            "evaluated_count": len(candidates_raw),
            "retired_implementations": executed,
            "retired_specs": retired_specs,
            "protected_canonical": protected,
            "skipped_batch_limit": skipped,
            "regime_deferred": deferred,
        }

    def _check_and_retire_spec(self, spec_id: str) -> Optional[RetirementDecision]:
        """Check if a spec should be retired after implementation retirements."""
        try:
            conn = self._pg._get_connection()
            cur = conn.cursor()

            cur.execute(
                "SELECT spec_id, name, source FROM strategy_specs WHERE spec_id = %s",
                (spec_id,),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                conn.close()
                return None

            spec = Spec(spec_id=str(row[0]), name=row[1], source=row[2])

            cur.execute(
                "SELECT COUNT(*) FROM strategy_implementations WHERE spec_id = %s AND status != 'RETIRED'",
                (spec_id,),
            )
            active_count = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM strategy_implementations WHERE spec_id = %s",
                (spec_id,),
            )
            total_count = cur.fetchone()[0]

            cur.close()
            conn.close()

            decision = evaluate_spec(spec, active_count, total_count)
            if decision.should_retire:
                result = self._pg.retire_spec(spec_id, decision.reason)
                if result.success:
                    return decision
            return None
        except Exception as e:
            logging.error("Failed to check spec %s for retirement: %s", spec_id, e)
            return None

    def reactivate_implementation(
        self, impl_id: str, reason: str, requester: str
    ) -> dict:
        """Reactivate a retired implementation after validation checks."""
        retirement_info = self._pg.get_retirement_info(impl_id)
        if not retirement_info:
            return {"success": False, "error": "No retirement record found"}

        days_since = (
            datetime.now(timezone.utc)
            - retirement_info["retired_at"].replace(tzinfo=timezone.utc)
        ).days
        reactivation_count = self._pg.get_reactivation_count(impl_id)
        config = self._config.retirement

        eligible, msg = can_reactivate(
            reactivation_count=reactivation_count,
            days_since_retirement=days_since,
            can_reactivate_flag=retirement_info["can_reactivate"],
            config=config,
        )

        if not eligible:
            return {"success": False, "error": msg}

        result = self._pg.reactivate_implementation(impl_id, reason, requester)
        return {
            "success": result.success,
            "details": result.details,
            "error": result.error,
        }

    def run_db_maintenance(self) -> list:
        """Run database maintenance tasks."""
        logging.info("Starting database maintenance")
        config = self._config.maintenance
        results = []

        # PostgreSQL maintenance
        results.extend(self._pg.vacuum_analyze(config.vacuum_tables))
        results.append(self._pg.cleanup_stale_signals(config.stale_signal_days))
        results.append(self._pg.cleanup_stale_backtests(config.stale_backtest_days))
        results.append(self._pg.cleanup_orphaned_records())

        # InfluxDB maintenance
        if self._influx:
            results.append(self._influx.check_retention_policies(config.influx_bucket))
            results.append(
                self._influx.downsample_old_data(
                    config.influx_bucket,
                    config.raw_retention_days,
                    f"{config.influx_bucket}_downsampled",
                )
            )

        logging.info("Database maintenance complete: %d operations", len(results))
        return results

    def run_health_checks(self) -> list:
        """Run health checks on all services."""
        logging.info("Starting health checks")
        results = self._health.check_all()
        summary = HealthChecker.summarize(results)
        logging.info(
            "Health checks complete: %d/%d healthy",
            summary["healthy"],
            summary["total"],
        )
        return results

    def run_state_repairs(self) -> list:
        """Run state repair checks."""
        logging.info("Starting state repairs")
        results = self._repairer.run_all_repairs()
        total_found = sum(r.inconsistencies_found for r in results)
        total_repaired = sum(r.repaired for r in results)
        logging.info(
            "State repairs complete: found=%d, repaired=%d", total_found, total_repaired
        )
        return results

    def run_log_rotation(self) -> list:
        """Run log rotation and cleanup."""
        logging.info("Starting log rotation")
        results = self._log_rotator.run()
        rotated = sum(1 for r in results if r.action == "rotated" and r.success)
        deleted = sum(1 for r in results if r.action == "deleted" and r.success)
        logging.info(
            "Log rotation complete: %d rotated, %d deleted", rotated, deleted
        )
        return results

    def get_dashboard_data(self) -> dict:
        """Get dashboard data for the admin UI."""
        return self._dashboard.get_dashboard_json()

    def run_full_cycle(self) -> JanitorReport:
        """Run a full janitor maintenance cycle and generate a report."""
        start = time.time()
        report = JanitorReport(report_date=date.today())

        # 1. Retirement evaluation
        try:
            retirement_results = self.run_retirement_cycle()
            report.evaluated_count = retirement_results["evaluated_count"]
            report.retired_implementations = retirement_results[
                "retired_implementations"
            ]
            report.retired_specs = retirement_results["retired_specs"]
            report.protected_canonical = retirement_results["protected_canonical"]
            report.skipped_batch_limit = retirement_results["skipped_batch_limit"]
            report.regime_deferred = retirement_results["regime_deferred"]
        except Exception as e:
            logging.error("Retirement cycle failed: %s", e)

        # 2. Database maintenance
        try:
            report.maintenance_results = self.run_db_maintenance()
        except Exception as e:
            logging.error("Database maintenance failed: %s", e)

        # 3. Health checks
        try:
            report.health_results = self.run_health_checks()
        except Exception as e:
            logging.error("Health checks failed: %s", e)

        # 4. State repairs
        try:
            report.repair_results = self.run_state_repairs()
        except Exception as e:
            logging.error("State repairs failed: %s", e)

        # 5. Log rotation
        try:
            report.log_rotation_results = self.run_log_rotation()
        except Exception as e:
            logging.error("Log rotation failed: %s", e)

        report.duration_seconds = time.time() - start

        # Save report to database
        try:
            self._pg.save_report(report.to_dict())
        except Exception as e:
            logging.error("Failed to save report: %s", e)

        # Distribute report to configured channels
        try:
            distribution_results = self._distributor.distribute(report)
            if distribution_results:
                logging.info(
                    "Report distributed to: %s",
                    ", ".join(distribution_results.keys()),
                )
        except Exception as e:
            logging.error("Failed to distribute report: %s", e)

        logging.info(
            "Full janitor cycle complete in %.1fs: retired=%d impls, %d specs",
            report.duration_seconds,
            report.retired_count,
            len(report.retired_specs),
        )

        return report
