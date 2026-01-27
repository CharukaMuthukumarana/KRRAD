# ml_engine/train_lstm.py
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

# 1. Define LSTM Architecture
class AttackLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes):
        super(AttackLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # LSTM Layer
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        # Fully Connected Layer (Classifier)
        self.fc = nn.Linear(hidden_size, num_classes)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        # Initialize hidden state
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # Forward propagate LSTM
        out, _ = self.lstm(x, (h0, c0))
        
        # Decode the hidden state of the last time step
        out = self.fc(out[:, -1, :])
        return self.sigmoid(out)

# 2. Training Loop
def train():
    print("Loading Sequences...")
    X = torch.load('ml_engine/data/lstm_X.pt')
    y = torch.load('ml_engine/data/lstm_y.pt').unsqueeze(1) # Shape fix
    
    # Dataset
    dataset = TensorDataset(X, y)
    dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
    
    # Model Init
    model = AttackLSTM(input_size=5, hidden_size=64, num_layers=2, num_classes=1)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    print("Training LSTM (Prediction Engine)...")
    for epoch in range(5): # 5 Epochs is enough for this demo
        for batch_X, batch_y in dataloader:
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
        print(f"Epoch {epoch+1} Complete. Loss: {loss.item():.4f}")
        
    # Save
    torch.save(model.state_dict(), 'ml_engine/models/lstm_model.pth')
    print("LSTM Model Saved to ml_engine/models/lstm_model.pth")

if __name__ == "__main__":
    train()