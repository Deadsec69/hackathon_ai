#!/bin/bash

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start components in separate terminals
# Note: You'll need to have tmux installed

tmux new-session -d -s ai-agent

# Split window into panes
tmux split-window -h
tmux split-window -v
tmux select-pane -t 0
tmux split-window -v

# Start app in pane 0
tmux select-pane -t 0
tmux send-keys "cd src/app && python app.py" C-m

# Start simulator in pane 1
tmux select-pane -t 1
tmux send-keys "cd src/simulator && python simulator.py" C-m

# Start agent in pane 2
tmux select-pane -t 2
tmux send-keys "cd src/agent && python main.py" C-m

# Start chatbot in pane 3
tmux select-pane -t 3
tmux send-keys "cd src/chatbot && python api.py" C-m

# Attach to tmux session
tmux attach-session -t ai-agent
