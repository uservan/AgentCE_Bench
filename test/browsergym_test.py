import gymnasium as gym
import browsergym.workarena  # register workarena tasks as gym environments

# start a workarena task
env = gym.make("browsergym/workarena.servicenow.order-ipad-pro")

# list all the available workarena tasks
env_ids = [id for id in gym.envs.registry.keys() if id.startswith("browsergym/workarena")]
print("\n".join(env_ids))