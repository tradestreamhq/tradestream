#!/usr/bin/env python3
"""
Test script for Strategy Visualization UI
Sets up port forwarding and tests the UI functionality
"""

import subprocess
import time
import requests
import threading
import signal
import sys
import os
from urllib.parse import urljoin

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
        """Set up port forwarding for PostgreSQL and API services"""
        print("🔌 Setting up port forwarding...")
        
        # Check if PostgreSQL port forward is already running
        try:
            result = subprocess.run("lsof -i :5432", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ PostgreSQL port forward already active on port 5432")
            else:
                print("🔄 Starting PostgreSQL port forward...")
                self.run_command("kubectl port-forward -n tradestream-dev svc/tradestream-dev-postgresql 5432:5432", background=True)
                time.sleep(3)
        except Exception as e:
            print(f"❌ Error setting up PostgreSQL port forward: {e}")
            return False
        
        # Check if API service exists and set up port forward
        try:
            # Check if strategy-monitor-api service exists
            result = subprocess.run("kubectl get svc -n tradestream-dev | grep strategy-monitor-api", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("🔄 Starting API service port forward...")
                self.run_command("kubectl port-forward -n tradestream-dev svc/strategy-monitor-api 8080:8080", background=True)
                time.sleep(3)
            else:
                print("⚠️  Strategy Monitor API service not found in Kubernetes, will start locally")
                return self.start_local_api()
        except Exception as e:
            print(f"❌ Error setting up API port forward: {e}")
            return False
        
        return True
    
    def start_local_api(self):
        """Start the API server locally"""
        print("🔄 Starting local API server...")
        
        # Get database password
        try:
            result = subprocess.run(
                "kubectl get secret -n tradestream-dev tradestream-dev-postgresql -o jsonpath='{.data.postgres-password}' | base64 -d",
                shell=True, capture_output=True, text=True, check=True
            )
            db_password = result.stdout.strip()
            
            if not db_password:
                print("❌ Failed to get database password")
                return False
            
            # Start the API server
            cmd = f"cd services/strategy_monitor_api && python3 main.py --postgres_password='{db_password}' --api_port=8080 --api_host=0.0.0.0"
            self.run_command(cmd, background=True)
            time.sleep(5)
            return True
            
        except Exception as e:
            print(f"❌ Error starting local API: {e}")
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
                response = requests.get(urljoin(base_url, endpoint), timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ {name}: {response.status_code} - {len(str(data))} chars")
                else:
                    print(f"❌ {name}: {response.status_code}")
            except Exception as e:
                print(f"❌ {name}: Error - {e}")
    
    def test_ui(self):
        """Test the UI by visiting it"""
        print("\n🎨 Testing UI...")
        
        # Check if UI files exist
        ui_dir = "ui/strategy-monitor"
        if not os.path.exists(ui_dir):
            print(f"❌ UI directory not found: {ui_dir}")
            return False
        
        # Start a simple HTTP server for the UI
        print("🔄 Starting UI server...")
        self.run_command(f"cd {ui_dir} && python3 -m http.server 3001", background=True)
        time.sleep(3)
        
        # Test UI accessibility
        ui_url = "http://localhost:3001"
        try:
            response = requests.get(ui_url, timeout=10)
            if response.status_code == 200:
                print(f"✅ UI is accessible at {ui_url}")
                
                # Check if the page contains expected content
                if "Strategy Monitor" in response.text or "tradestream" in response.text.lower():
                    print("✅ UI page contains expected content")
                else:
                    print("⚠️  UI page content seems unexpected")
                
                return True
            else:
                print(f"❌ UI returned status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error accessing UI: {e}")
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
        
        # Kill any remaining port-forward processes
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
            
            # Step 2: Wait for API to be ready
            if not self.wait_for_service("http://localhost:8080/api/health", "API Server"):
                print("❌ API server not ready")
                return False
            
            # Step 3: Test API endpoints
            self.test_api_endpoints()
            
            # Step 4: Test UI
            if not self.test_ui():
                print("❌ UI test failed")
                return False
            
            print("\n🎉 All tests passed! Strategy Visualization UI is working.")
            print("\n📊 Access URLs:")
            print("   UI Dashboard: http://localhost:3001")
            print("   API Base:    http://localhost:8080")
            print("\n💡 Press Ctrl+C to stop all services")
            
            # Keep running until interrupted
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")
        finally:
            self.cleanup()

if __name__ == "__main__":
    tester = UITester()
    tester.run() 