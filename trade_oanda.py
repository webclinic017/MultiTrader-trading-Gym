

import warnings
warnings.filterwarnings("ignore")

warnings.filterwarnings("ignore",category=ResourceWarning)


from environments.live_environments import BaseLiveTradingEnv
from neuralforecast.core import NeuralForecast
from configs import defaults
from Keys import *
import pickle
import numpy as np
from utils import pearl_utils
from Pearl.pearl.utils.instantiations.environments.gym_environment import \
    GymEnvironment
import boto3
import shutil
import tempfile
from IPython.display import display
with tempfile.TemporaryDirectory() as temp_dir:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        from configs import fx_defaults as defaults



        base_asset=defaults.base_asset
        quote_asset=defaults.quote_asset
        test_net=False
        time_frame=defaults.time_frame

        product_type=defaults.product_type
        futures_target='DOG-29NOV24-CDE'
        exchange=defaults.exchange
        trade_target='/'.join([base_asset,quote_asset]) 
        agent_path=defaults.agent_path


        s3= boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_KEY)

        print('Downloading files from S3')
        print(f'Downloading {defaults.forecasting_model_path}')
        s3.download_file('coinbasetradehistory','trade.db','Trade_history/trade.db')

        print(f'Downloading {defaults.forecasting_model_path}')
        s3.download_file('coinbasetradehistory',defaults.forecasting_model_path,defaults.forecasting_model_path)

        print(f'Downloading {agent_path}')
        s3.download_file('coinbasetradehistory',agent_path,agent_path)

        agent=pickle.load(open(agent_path,'rb'))
        forecast_model=NeuralForecast.load(defaults.forecasting_model_path)

        live_env=BaseLiveTradingEnv(
                    api_key=coinbase_api_key,
                    api_secret=coinbase_api_secret,
                    paper=test_net,
                    symbol=trade_target,
                    time_frame=time_frame,
                    product_type=product_type,
                    positions=[0,1],
                    history_path='Trade_history/trade.db',
                    exchange=exchange,
                    forecast_model=forecast_model,
                    discord_webhook=discord_forex_webhook,

                    )

        live_pearl_env=GymEnvironment(live_env)


                
        observation,action_space=live_pearl_env.reset()
        # agent.reset(observation, action_space)
        current_position=int(live_env.client.get_current_position())
        # action=agent.act(exploit=True)
        live_pearl_env.env.allow_trade_submit=False
        action=live_env.action_map[current_position]
        action_result=live_pearl_env.step(action=current_position)

        live_pearl_env.env.allow_trade_submit=True
        agent.observe(action_result)
        action=agent.act(exploit=True)
        live_pearl_env.step(action)
        
        s3.upload_file('Trade_history/trade.db','coinbasetradehistory','trade.db',)
        s3.upload_file(agent_path,'coinbasetradehistory',agent_path)
        s3.upload_file(defaults.forecasting_model_path,'coinbasetradehistory',defaults.forecasting_model_path)

        display(live_env.client.account())










