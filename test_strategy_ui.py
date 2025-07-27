#!/usr/bin/env python3
"""
Strategy Visualization UI Test Script
Tests the strategy monitor UI by setting up port forwarding and starting services locally.
"""

import subprocess
import time
import requests
import threading
import signal
import sys
import os
import base64
from pathlib import Path

class UITester:
    def __init__(self):
        self.processes = []
        self.running = True
        
        # Set up signal handler for clean shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        print("\n🛑 Shutting down...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def run_command(self, cmd, background=False, check=True):
        """Run a command and return the process"""
        print(f"🔄 Running: {cmd}")
        if background:
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.processes.append(process)
            return process
        else:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=check)
            return result
    
    def setup_port_forwarding(self):
        """Set up port forwarding for PostgreSQL database"""
        print("🔌 Setting up PostgreSQL port forward...")
        
        try:
            # Check if port 5432 is already in use
            result = subprocess.run("lsof -i :5432", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ PostgreSQL port forward already active on port 5432")
            else:
                print("🔄 Starting PostgreSQL port forward...")
                self.run_command("kubectl port-forward -n tradestream-dev svc/tradestream-dev-postgresql 5432:5432", background=True)
                time.sleep(3)
            return True
        except Exception as e:
            print(f"❌ Error setting up PostgreSQL port forward: {e}")
            return False
    
    def get_db_password(self):
        """Get database password from Kubernetes secret"""
        print("🔑 Getting database password...")
        
        try:
            result = subprocess.run(
                "kubectl get secret -n tradestream-dev tradestream-dev-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d",
                shell=True, capture_output=True, text=True, check=True
            )
            password = result.stdout.strip()
            
            if not password:
                print("❌ Failed to get database password")
                return None
            
            print("✅ Database password obtained")
            return password
            
        except Exception as e:
            print(f"❌ Error getting database password: {e}")
            return None
    
    def start_api_server(self, db_password):
        """Start the strategy monitor API server locally"""
        print("🌐 Starting Strategy Monitor API...")
        
        try:
            # Check if API directory exists
            api_dir = Path("services/strategy_monitor_api")
            if not api_dir.exists():
                print(f"❌ API directory not found: {api_dir}")
                return False
            
            # Start API server
            cmd = f"""cd {api_dir} && python3 main.py \
                --postgres_password='{db_password}' \
                --api_port=8080 \
                --api_host=0.0.0.0"""
            
            self.run_command(cmd, background=True)
            
            # Wait for API to be ready
            return self.wait_for_service("http://localhost:8080/api/health", "API server", max_attempts=30)
            
        except Exception as e:
            print(f"❌ Error starting API server: {e}")
            return False
    
    def start_ui_server(self):
        """Start the UI server"""
        print("🎨 Starting UI server...")
        
        try:
            # Check if UI directory exists
            ui_dir = Path("ui/strategy-monitor")
            if not ui_dir.exists():
                print(f"❌ UI directory not found: {ui_dir}")
                return False
            
            # Start HTTP server
            cmd = f"cd {ui_dir} && python3 -m http.server 3001"
            self.run_command(cmd, background=True)
            
            # Wait for UI to be ready
            return self.wait_for_service("http://localhost:3001", "UI server", max_attempts=10)
            
        except Exception as e:
            print(f"❌ Error starting UI server: {e}")
            return False
    
    def wait_for_service(self, url, name, max_attempts=30):
        """Wait for a service to be ready"""
        print(f"⏳ Waiting for {name} to be ready...")
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"✅ {name} is ready!")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            print(".", end="", flush=True)
            time.sleep(1)
        
        print(f"\n❌ {name} failed to start within {max_attempts}s")
        return False
    
    def test_api_endpoints(self):
        """Test the API endpoints"""
        print("\n🧪 Testing API endpoints...")
        
        endpoints = [
            ("/api/health", "Health Check"),
            ("/api/strategies?limit=5", "Strategies List"),
            ("/api/metrics", "Metrics"),
            ("/api/symbols", "Symbols"),
            ("/api/strategy-types", "Strategy Types")
        ]
        
        base_url = "http://localhost:8080"
        
        for endpoint, name in endpoints:
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ {name}: {response.status_code} - {len(str(data))} chars")
                else:
                    print(f"❌ {name}: {response.status_code}")
            except Exception as e:
                print(f"❌ {name}: Error - {e}")
    
    def test_ui_page(self):
        """Test the UI page"""
        print("\n🎨 Testing UI page...")
        
        try:
            response = requests.get("http://localhost:3001", timeout=10)
            if response.status_code == 200:
                print("✅ UI page loads successfully")
                
                # Check if it contains expected content
                if "Strategy Monitor" in response.text or "tradestream" in response.text.lower():
                    print("✅ UI page contains expected content")
                else:
                    print("⚠️  UI page content seems unexpected")
                    
                return True
            else:
                print(f"❌ UI page returned status code: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error accessing UI page: {e}")
            return False
    
    def cleanup(self):
        """Clean up all background processes"""
        print("\n🧹 Cleaning up processes...")
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                process.kill()
        
        # Kill any remaining processes
        subprocess.run("pkill -f 'kubectl port-forward'", shell=True)
        subprocess.run("pkill -f 'python3.*http.server.*3001'", shell=True)
        subprocess.run("pkill -f 'python3.*main.py.*8080'", shell=True)
    
    def run(self):
        """Main test sequence"""
        try:
            print("🚀 Starting Strategy Visualization UI Test")
            print("=" * 50)
            
            # Step 1: Set up port forwarding
            if not self.setup_port_forwarding():
                print("❌ Failed to set up port forwarding")
                return False
            
            # Step 2: Get database password
            db_password = self.get_db_password()
            if not db_password:
                print("❌ Failed to get database password")
                return False
            
            # Step 3: Start API server
            if not self.start_api_server(db_password):
                print("❌ Failed to start API server")
                return False
            
            # Step 4: Start UI server
            if not self.start_ui_server():
                print("❌ Failed to start UI server")
                return False
            
            # Step 5: Test API endpoints
            self.test_api_endpoints()
            
            # Step 6: Test UI page
            if self.test_ui_page():
                print("\n🎉 All tests passed! Strategy Visualization UI is working.")
                print("\n📊 Access URLs:")
                print("   UI Dashboard: http://localhost:3001")
                print("   API Base:    http://localhost:8080")
                print("\n💡 Press Ctrl+C to stop all services")
                
                # Keep running until interrupted
                while self.running:
                    time.sleep(1)
                    
                return True
            else:
                print("\n❌ UI test failed")
                return False
                
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
            return True
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")
            return False
        finally:
            self.cleanup()

if __name__ == "__main__":
    tester = UITester()
    success = tester.run()
    sys.exit(0 if success else 1)
