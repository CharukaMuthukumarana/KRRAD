import numpy as np
import gym
from gym import spaces

class K8sSecurityEnv(gym.Env):
    def __init__(self):
        super(K8sSecurityEnv, self).__init__()
        
        # Actions: 0=Wait, 1=Block (eBPF), 2=Scale (K8s HPA)
        self.action_space = spaces.Discrete(3)
        
        # State: [PPS (Normalized), BPS (Normalized), CPU Load, ML_Threat_Score]
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(4,), dtype=np.float32)
        
        self.state = None
        self.steps = 0
        self.max_capacity = 1.0
        
    def reset(self):
        # Start in a normal benign state
        self.state = np.array([0.1, 0.1, 0.2, 0.05], dtype=np.float32)
        self.steps = 0
        return self.state

    def step(self, action):
        self.steps += 1
        pkt_rate, byte_rate, cpu, ml_score = self.state
        
        # 1. Background Traffic Dynamics
        actual_threat_present = ml_score > 0.6
        
        reward = 0
        
        # 2. Execute Action & Calculate Reward
        if action == 1: # Block IP via eBPF
            if actual_threat_present:
                pkt_rate *= 0.05
                byte_rate *= 0.05
                reward = 10 # Reward for successfully blocking an attack
            else:
                reward = -15 # Heavy penalty for blocking when no attack is present (false positive)
                
        elif action == 2: # Scale Up via Kubernetes
            self.max_capacity += 0.5 # Increase server capacity
            reward = 2 if cpu > 0.7 else -2
            
        else: # Wait
            if actual_threat_present:
                reward = -10 # Penalty for ignoring an attack
            else:
                reward = 1   # Small reward for saving resources during peacetime

        # 3. Simulate Next
        if np.random.rand() < 0.1:
            ml_score = np.random.uniform(0.7, 0.99) # ML detects anomaly
            pkt_rate = np.random.uniform(0.7, 1.0)
            byte_rate = np.random.uniform(0.7, 1.0)
        elif np.random.rand() < 0.1:
            ml_score = np.random.uniform(0.01, 0.2) # Peace returns
            pkt_rate = np.random.uniform(0.05, 0.2)
            byte_rate = np.random.uniform(0.05, 0.2)
            self.max_capacity = 1.0 # Replicas scale back down eventually

        # 4. Queueing Theory CPU Calculation
        cpu = min(1.0, pkt_rate / self.max_capacity)
        
        pkt_rate = np.clip(pkt_rate + np.random.normal(0, 0.02), 0, 1)
        byte_rate = np.clip(byte_rate + np.random.normal(0, 0.02), 0, 1)
        cpu = np.clip(cpu + np.random.normal(0, 0.05), 0, 1)
        
        self.state = np.array([pkt_rate, byte_rate, cpu, ml_score], dtype=np.float32)
        done = self.steps >= 50
        
        return self.state, reward, done, {}