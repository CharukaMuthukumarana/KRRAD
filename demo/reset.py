import subprocess

print("📉 Scaling down 'krrad-target' to 1 replica...")
subprocess.run("kubectl scale deployment krrad-target --replicas=1", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # nosec

print("🧹 Flushing eBPF Blacklists...")
pod_name = subprocess.getoutput("kubectl get pod -n kube-system -l app=krrad-sensor -o jsonpath='{.items[0].metadata.name}'")

if pod_name:
    # Using python3 inside the container to make the POST request instead of curl
    unblock_cmd = f"kubectl exec -n kube-system {pod_name} -- python3 -c \"import urllib.request; req = urllib.request.Request('http://localhost:5000/unblock_all', method='POST'); print(urllib.request.urlopen(req).read().decode('utf-8'))\""
    result = subprocess.getoutput(unblock_cmd)
    print(f"✅ API Response: {result}")
else:
    print("❌ Sensor pod not found.")
