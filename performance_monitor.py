#!/usr/bin/env python3
"""
Performance monitoring script for the Telegram Flight Bot
"""
import psutil
import time
import json
import sys
import subprocess
from datetime import datetime

def monitor_process(pid, output_file="performance_metrics.json"):
    """Monitor a process and collect performance metrics"""
    try:
        process = psutil.Process(pid)
        start_time = time.time()
        start_cpu_time = process.cpu_times()
        start_memory = process.memory_info()
        
        metrics = {
            "start_time": datetime.now().isoformat(),
            "pid": pid,
            "command": " ".join(process.cmdline()),
            "samples": []
        }
        
        print(f"Monitoring process {pid}: {process.name()}")
        print("Time\t\tCPU%\tMemory(MB)\tThreads\tFiles")
        print("-" * 60)
        
        sample_count = 0
        while process.is_running():
            try:
                # Get current metrics
                cpu_percent = process.cpu_percent(interval=1)
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                num_threads = process.num_threads()
                num_fds = len(process.open_files()) if hasattr(process, 'open_files') else 0
                
                timestamp = time.time() - start_time
                
                sample = {
                    "timestamp": timestamp,
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb,
                    "memory_bytes": memory_info.rss,
                    "num_threads": num_threads,
                    "num_files": num_fds
                }
                
                metrics["samples"].append(sample)
                
                # Print current status
                print(f"{timestamp:7.1f}s\t{cpu_percent:5.1f}%\t{memory_mb:8.1f}\t{num_threads:5d}\t{num_fds:5d}")
                
                sample_count += 1
                time.sleep(2)  # Sample every 2 seconds
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
        
        # Calculate final metrics
        end_time = time.time()
        end_cpu_time = process.cpu_times() if process.is_running() else None
        
        metrics["end_time"] = datetime.now().isoformat()
        metrics["total_runtime"] = end_time - start_time
        metrics["total_samples"] = sample_count
        
        if metrics["samples"]:
            metrics["peak_memory_mb"] = max(s["memory_mb"] for s in metrics["samples"])
            metrics["avg_cpu_percent"] = sum(s["cpu_percent"] for s in metrics["samples"]) / len(metrics["samples"])
            metrics["max_threads"] = max(s["num_threads"] for s in metrics["samples"])
            metrics["max_files"] = max(s["num_files"] for s in metrics["samples"])
        
        # Save metrics to file
        with open(output_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        print(f"\nProcess completed. Metrics saved to {output_file}")
        print(f"Total runtime: {metrics['total_runtime']:.2f} seconds")
        if metrics["samples"]:
            print(f"Peak memory usage: {metrics['peak_memory_mb']:.1f} MB")
            print(f"Average CPU usage: {metrics['avg_cpu_percent']:.1f}%")
        
        return metrics
        
    except psutil.NoSuchProcess:
        print(f"Process {pid} not found")
        return None
    except Exception as e:
        print(f"Error monitoring process: {e}")
        return None

def run_app_with_monitoring():
    """Run the app.py script and monitor its performance"""
    print("Starting app.py with performance monitoring...")
    
    # Start the app process
    cmd = ["/usr/local/bin/python3", "app.py"]
    process = subprocess.Popen(cmd, cwd="/Users/esemb/Desktop/code/telegram-bot-pasajes")
    
    print(f"Started process with PID: {process.pid}")
    
    # Monitor the process
    try:
        metrics = monitor_process(process.pid)
        process.wait()  # Wait for process to complete
        return metrics, process.returncode
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        process.terminate()
        return None, -1

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        # Monitor existing process
        pid = int(sys.argv[1])
        monitor_process(pid)
    else:
        # Run and monitor app.py
        metrics, return_code = run_app_with_monitoring()
        print(f"\nApp.py finished with return code: {return_code}")
