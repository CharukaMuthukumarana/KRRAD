import subprocess
import time

print("🔄 KRRAD: System Reset & Cleanup")
print("--------------------------------------------------")

# 1. Reset Target Scaling
print("📉 Scaling down 'krrad-target' to 1 replica...")
subprocess.run("kubectl scale deployment krrad-target --replicas=1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 2. Unblock IPs
print("🧹 Flushing eBPF Blacklists...")
pod_name = subprocess.getoutput("kubectl get pod -n kube-system -l app=krrad-sensor -o jsonpath='{.items[0].metadata.name}'")

if "krrad-sensor" in pod_name:
    # We use Python's urllib inside the container instead of curl to guarantee it executes
    unblock_cmd = f"""kubectl exec -n kube-system {pod_name} -- python3 -c "import urllib.request; req = urllib.request.Request('http://localhost:5000/unblock_all', method='POST'); res = urllib.request.urlopen(req); print(res.read().decode('utf-8'))" """
    
    result = subprocess.getoutput(unblock_cmd)
    print(f"✅ Unblock API Response: {result}")
else:
    print("❌ Critical Error: Could not find krrad-sensor pod!")

# 3. Wait for Target
try:
    subprocess.run("kubectl wait --for=condition=ready pod -l app=krrad-target --timeout=60s", 
                   shell=True, check=True, stdout=subprocess.DEVNULL)
except:
    pass

print("--------------------------------------------------")
print("✅ SYSTEM RESET COMPLETE.")
