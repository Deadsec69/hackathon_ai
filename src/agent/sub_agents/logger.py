import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[
                       logging.StreamHandler(sys.stdout)
                   ])

# Create main agent logger
logger = logging.getLogger("agent")

# Create specialized agent loggers
seer_logger = logging.getLogger("agent.seer")
medic_logger = logging.getLogger("agent.medic")
forge_logger = logging.getLogger("agent.forge")
smith_logger = logging.getLogger("agent.smith")
vision_logger = logging.getLogger("agent.vision")
herald_logger = logging.getLogger("agent.herald")
oracle_logger = logging.getLogger("agent.oracle")
