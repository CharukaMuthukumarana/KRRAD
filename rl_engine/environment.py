# rl_engine/environment.py
import numpy as np
import gym
from gym import spaces

class K8sSecurityEnv(gym.Env):
    def __init__(self):
        super(K8sSecurityEnv, self).__init__()
        
        # Actions: 0=No-Op, 1=Block IP, 2=Scale Up Pods
        self.action_space = spaces.Discrete(3)
        
        # State: [Packet Rate, Byte Rate, CPU Load, Active Attack?]
        # We normalize these values between 0 and 1 for the AI
        self.observation_space = spaces.Box(low=0, high=1, shape=(4,), dtype=np.float32)
        
        self.state = None
        self.steps = 0
        
    def reset(self):
        # Start with a random "normal" state
        self.state = np.array([0.1, 0.1, 0.2, 0.0], dtype=np.float32)
        self.steps = 0
        return self.state

    def step(self, action):
        self.steps += 1
        
        # Extract current state
        pkt_rate, byte_rate, cpu, is_attack = self.state
        
        # 1. SIMULATE ENVIRONMENT REACTION
        
        # If Action is "Block IP" (1)
        if action == 1:
            if is_attack > 0.5:
                # Good move! Attack blocked.
                pkt_rate *= 0.1 
                byte_rate *= 0.1
                cpu *= 0.5
                reward = 10 
            else:
                # Bad move! You blocked a normal user.
                reward = -5

        # If Action is "Scale Up" (2)
        elif action == 2:
            # CPU load goes down, but traffic stays same
            cpu *= 0.6 
            reward = 2 if cpu > 0.8 else -1 # Only reward if CPU was actually high
            
        # If Action is "No-Op" (0)
        else:
            if is_attack > 0.5:
                # Bad! Doing nothing during attack.
                cpu = min(1.0, cpu + 0.2) # CPU spikes
                reward = -10
            else:
                # Good! Doing nothing when peaceful.
                reward = 5

        # Randomly inject new traffic patterns for next step
        # 10% chance of an attack starting
        if np.random.rand() < 0.1:
            is_attack = 1.0
            pkt_rate = 0.9
            byte_rate = 0.9
            cpu = 0.9
        
        self.state = np.array([pkt_rate, byte_rate, cpu, is_attack], dtype=np.float32)
        
        # Done if we survived 50 steps
        done = self.steps >= 50
        
        return self.state, reward, done, {}