# rl_engine/train_agent.py
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from environment import K8sSecurityEnv
import random
from collections import deque

# 1. Define the Neural Network
class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim)
        )

    def forward(self, x):
        return self.fc(x)

# 2. Training Setup
env = K8sSecurityEnv()
model = DQN(env.observation_space.shape[0], env.action_space.n)
optimizer = optim.Adam(model.parameters(), lr=0.001)
criterion = nn.MSELoss()

# Replay Buffer to remember past lessons
memory = deque(maxlen=2000)
epsilon = 1.0  # Exploration rate (start curious)
epsilon_decay = 0.995
epsilon_min = 0.01
gamma = 0.99   # Discount factor

def train_dqn(episodes=500):
    global epsilon
    print("Training RL Agent (DQN)... This simulates the 'Learning' phase.")
    
    for e in range(episodes):
        state = env.reset()
        total_reward = 0
        
        while True:
            # Epsilon-Greedy Strategy
            if np.random.rand() <= epsilon:
                action = env.action_space.sample() # Explore
            else:
                with torch.no_grad():
                    q_values = model(torch.FloatTensor(state))
                    action = torch.argmax(q_values).item() # Exploit
            
            # Take action
            next_state, reward, done, _ = env.step(action)
            
            # Save to memory
            memory.append((state, action, reward, next_state, done))
            state = next_state
            total_reward += reward
            
            if done:
                break
            
            # Learn from memory (Experience Replay)
            if len(memory) > 32:
                batch = random.sample(memory, 32)
                for s, a, r, ns, d in batch:
                    target = r
                    if not d:
                        target = r + gamma * torch.max(model(torch.FloatTensor(ns))).item()
                    
                    target_f = model(torch.FloatTensor(s))
                    target_val = target_f.clone().detach()
                    target_val[a] = target
                    
                    optimizer.zero_grad()
                    loss = criterion(target_f, target_val)
                    loss.backward()
                    optimizer.step()

        # Decay exploration
        if epsilon > epsilon_min:
            epsilon *= epsilon_decay
            
        if e % 50 == 0:
            print(f"Episode {e}/{episodes} - Reward: {total_reward:.2f} - Epsilon: {epsilon:.2f}")

    # Save the trained brain
    torch.save(model.state_dict(), "rl_engine/models/dqn_agent.pth")
    print("RL Agent saved to rl_engine/models/dqn_agent.pth")

if __name__ == "__main__":
    train_dqn()