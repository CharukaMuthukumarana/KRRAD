import numpy as np
import gym
from gym import spaces

class K8sSecurityEnv(gym.Env):
    def __init__(self):
        super(K8sSecurityEnv, self).__init__()
        
        # Actions: 0=Wait, 1=Block, 2=Scale
        self.action_space = spaces.Discrete(3)
        
        # State: [Packet Rate, Byte Rate, CPU Load, Active Attack]
        self.observation_space = spaces.Box(low=0, high=1, shape=(4,), dtype=np.float32)
        
        self.state = None
        self.steps = 0
        
    def reset(self):
        self.state = np.array([0.1, 0.1, 0.2, 0.0], dtype=np.float32)
        self.steps = 0
        return self.state

    def step(self, action):
        self.steps += 1
        pkt_rate, byte_rate, cpu, is_attack = self.state
        
        # Simulate Environment Dynamics
        if action == 1: # Block IP
            if is_attack > 0.5:
                pkt_rate *= 0.1 
                byte_rate *= 0.1
                cpu *= 0.5
                reward = 10 
            else:
                reward = -5 # Penalty for blocking legitimate traffic

        elif action == 2: # Scale Up
            cpu *= 0.6 
            reward = 2 if cpu > 0.8 else -1 
            
        else: # Wait
            if is_attack > 0.5:
                cpu = min(1.0, cpu + 0.2)
                reward = -10
            else:
                reward = 5

        # Stochastic Traffic Injection (10% chance of attack)
        if np.random.rand() < 0.1:
            is_attack = 1.0
            pkt_rate = 0.9
            byte_rate = 0.9
            cpu = 0.9
        
        self.state = np.array([pkt_rate, byte_rate, cpu, is_attack], dtype=np.float32)
        done = self.steps >= 50
        
        return self.state, reward, done, {}