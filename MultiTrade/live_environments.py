import sqlite3 as db

import numpy as np
import pandas as pd
from binance.spot import Spot
from utils.utils import preprocess_data, symbol_map

from .environments import NeuralForecastingTradingEnv


class LiveTradingEnv(NeuralForecastingTradingEnv):
    def __init__(
            self,
            api_key,
            api_secret,
            test_net=True,
            time_frame='1h',
            target_symbol='ETH/USDT',
            restore_trading=True,
            history_path='Trade_history/trade.db',
            *args,
            **kwargs,
            ):
        self.api_key=api_key
        self.api_secret=api_secret
        self.context_length=kwargs['model'].models[0].input_size
        kwargs['max_episode_duration']=self.context_length
        self.live_history=pd.DataFrame(columns=[
            'portfolio_valuation',
            'position',
            
            ])
        self._restore_trading=restore_trading
        
        self.conn = db.connect(history_path)

        self._n_steps=0
        self._trade_info=None
        self.min_quote_size=None
        self.max_quote_size=None
        self.min_asset_size=None
        self.max_asset_size=None
        self.quote_asset_precision=None
        self.base_asset_precision=None

        self.time_frame=time_frame
        self.action_map={x:pct for x,pct in enumerate(kwargs['positions'])}
        self.side_map={-1:'SELL',1:'BUY',0:'close'}
        self.test_net=test_net
        self.quote_asset=target_symbol.split('/')[-1]
        self.base_asset=target_symbol.split('/')[0]
        self.symbol=''.join([self.base_asset,self.quote_asset])
        self._rew=0
        self._current_valuation=0
        self.client=self.connect_client()

        self.account=self.get_account()
        self.initial_base_balance=self.get_balance(self.base_asset)
        self.initial_quote_balance=self.get_balance(self.quote_asset)
        self.set_trade_rules()
        self.cash=self.initial_base_balance
        data=self.get_data()
        kwargs['df']=data
        kwargs['portfolio_initial_value']=self.initial_quote_balance



        super().__init__(*args,**kwargs)
        self.spec.id='LiveNeuralForecastingTradingEnv'
        self._fake_trade=super()._trade
        if self._restore_trading:
            self._load_history()

    def connect_client(self):

        if self.test_net:
            # self.stream_client = SpotWebsocketStreamClient(stream_url='wss://testnet.binance.vision')
            client=Spot(api_key=self.api_key,api_secret=self.api_secret,base_url='https://testnet.binance.vision')

        else:
            client=Spot(api_key=self.api_key,api_secret=self.api_secret,base_url='https://api3.binance.com')
        return client

    def set_trade_rules(self):
        trade_info=pd.DataFrame(self.client.exchange_info(self.symbol)['symbols'][0]['filters'])
        trade_info=trade_info.set_index('filterType')
        self._trade_info=trade_info
        
        self.min_quote_size=float(trade_info.loc['LOT_SIZE','minQty'])
        self.max_quote_size=float(trade_info.loc['LOT_SIZE','maxQty'])
        self.min_asset_size=float(trade_info.loc['MARKET_LOT_SIZE','minQty'])
        self.max_asset_size=float(trade_info.loc['MARKET_LOT_SIZE','maxQty'])
        
        self.quote_asset_precision=self.client.exchange_info(self.symbol)['symbols'][0]['quotePrecision']
        self.base_asset_precision=self.client.exchange_info(self.symbol)['symbols'][0]['baseAssetPrecision']

    def live_step(self,position_index,wait=True):

        if position_index is not None: self._take_action(self.positions[position_index])
        self._n_steps+=1
        self._step += 1
        self._idx = -1
        done, truncated = False, False
        if wait:
            self.wait_for_reward()
        
        portfolio_value = self._portfolio.valorisation(self._get_price())
        portfolio_distribution = self._portfolio.get_portfolio_distribution()

        if portfolio_value <= 1000:
            done = True

        if isinstance(self.max_episode_duration,int) and self._step >= self.max_episode_duration - 1:
            truncated = True

        reward = self.reward_function(self.historical_info)
        self.historical_info["reward", -1] = reward
        
        hist_config=self.build_history(reward=reward)
      
        self.historical_info.add(**hist_config)
        self._save_history()
                
        self._set_df(self.get_data())
        self._prep_forecasts()
        self._set_df(self.get_data())
        return self._get_obs(),  self.historical_info["reward", -1], done, truncated, self.historical_info[-1]

    def update_portfolio(self):
        self.account=self.get_account()
        base_balance=self.get_balance(self.base_asset)
        quote_balance=self.get_balance(self.quote_asset)
        self._portfolio.asset=base_balance
        self._portfolio.fiat=quote_balance
    
    def get_account(self):
        account=self.client.account()
        account_frame=pd.DataFrame(account['balances']).set_index('asset')
        return account_frame
    
    def get_balance(self,symbol):
        bal=self.account.loc[symbol]
        bal=bal['free']
        # print(bal)
        bal=float(bal)
        
        return bal
    
    def _get_price(self):
        price=float(self.client.ticker_price(self.symbol)['price'])
        self._current_price=price
        return price

    def _take_action(self, position):
        if position != self._position:
            self._trade(position)
        else:
            print('stay in position')
            
    def _trade(self, position, price = None):
        self.account=self.get_account()
        ## get size of assets we have
        n_dollars=self.get_balance(self.quote_asset)
        n_asset=self.get_balance(self.base_asset)
        price=self._get_price()
        
        new_position=position
    
        # position=self._portfolio.position(price)

        trade_from_to=[self._position,new_position]
        position_change=np.diff([trade_from_to])
        position_change=round(float(position_change),2)

        print(f'',position_change)

        ## decide which direction to go
        side=np.sign(position_change)
        side_str=self.side_map[side]
        self.update_portfolio()
        current_portfolio=self._portfolio.get_portfolio_distribution()
        current_portfolio['valuation']=self._portfolio.valorisation(price)
        

        params = {
            'symbol': self.symbol,
            'side':side_str,
            'type': 'MARKET',
            ## later we can expirement with limit orders
            # 'type': 'LIMIT',
            # 'timeInForce': 'GTC',
            # 'price':float(round(price,8))
            }
        
        if side_str.upper()=='BUY':
            dollar_val=np.abs(position_change)*n_dollars
            asset_size=n_dollars/price
            trade_size=self.normalize_quote_size(dollar_val)

        elif side_str.upper()=='SELL':
            asset_size=np.abs(position_change)*n_asset
            dollar_val=asset_size*price
            trade_size=self.normalize_quote_size(dollar_val)

        params['quoteOrderQty']=trade_size

        
        print('portfoliio',current_portfolio)

        print(f'''Trade {trade_from_to[0]}->{trade_from_to[1]}
              {position_change}, so {round(dollar_val,2)}{self.quote_asset}/ {asset_size}{self.base_asset},
              {side_str} {self.base_asset}:{asset_size} for {dollar_val:.2f}$ at {price} {self.symbol}'''
              )
        
        print(params)
        try: 
            self.client.new_order(**params)
        except Exception as e:
            print(e)
        self.update_portfolio()
        self._position = position
        return
    
    def normalize_asset_size(self,size):
        # balance=self.get_balance(self.base_asset)
        # current_dols=self.get_balance(self.quote_asset)
        size=float(size)
        size=max([self.min_asset_size,size]) # max of smallest possible trades
        size=min([self.max_asset_size,size])# min of largest possible trades eg. if we dont have enough currency to make a big trade sell everything
        size=round(size,self.base_asset_precision)
        return size
    
    def normalize_quote_size(self,size):
        # balance=self.get_balance(self.quote_asset)
        size=float(size)
        size=max([self.min_quote_size,size]) # max of smallest possible trades
        size=min([self.max_quote_size,size]) # min of largest possible trades eg. if we dont have enough currency to make a big trade sell everything 
        size=round(size,self.quote_asset_precision)
        return size
    
    def get_position(self,history):
        current_position=history['position',-1]
        return current_position

    def get_data(self):
        
        data_list=self.client.klines(self.symbol, self.time_frame, limit=self.context_length*2)
        columns=['date_open','open','high','low','close','volume','date_close','QA_volume','N_trades','BA_volume','BQ_volume','unused']
        data=pd.DataFrame(data_list,columns=columns)

        data['date_close']=data['date_close'].apply(pd.to_datetime,unit='ms')
        # data['date_close']=data['date_close'].apply(pd.Timestamp)
        data=data.set_index('date_close')
        data=data[['open','high','low','close','volume']]

        data=preprocess_data(data)

        data['ds']=data.index.copy()
        data['symbol'] = self.symbol
        data['unique_id']=symbol_map[self.symbol]

        return data

    def wait_for_reward(self):
        self.client=self.connect_client()
        current_time=pd.Timestamp(datetime.datetime.now())
        

        next_time=current_time+pd.Timedelta( self.time_frame)
        next_time=next_time.floor(self.time_frame)
        wait_time=(next_time-current_time).seconds
        self.update_portfolio()
        valuation=round(self._portfolio.valorisation(self._get_price()),2)
        bar=tqdm(range(wait_time))
        reward=round(self.historical_info["reward", -1],2)

        for i in bar:
            time.sleep(1)
            bar.set_description(f'position {self._position} value: {valuation:.2f},reward: {reward:.2f} waiting {int((wait_time-i)/60)} min for next reward')
            if i%60==0:
                self.update_portfolio()
                valuation=self._portfolio.valorisation(self._get_price())

        return

    def reset_account(self):
        ##update account
        self.account=self.get_account()
        price=self._get_price()
        ##Get current_valuation
        current_size=self.get_balance(self.base_asset)
        current_dols=self.get_balance(self.quote_asset)
        total_valuation=current_dols+current_size*price
        ##split in half to know how much to distribute to each side
        half_valuation=total_valuation/2
        split_asset=half_valuation/price
        
        dump_size=np.diff([split_asset,current_size])
        trade_size=abs(dump_size)
        dollar_val=trade_size*price
        dollar_val=self.normalize_quote_size(dollar_val)

        if dump_size>self.min_asset_size:
            
            params = {
                'symbol': self.symbol,
                'side':'SELL',
                'type': 'MARKET',
                'quoteOrderQty':dollar_val,
                # 'quantity':trade_size,
                }
            
            print('reset_account')
            print(params)
            self.client.new_order(**params)


        elif dump_size<self.min_asset_size:
            params = {
                'symbol': self.symbol,
                'side':'BUY',
                'type': 'MARKET',
                'quoteOrderQty':dollar_val,
                }
            
            print('reset_account')
            print(params)
            self.client.new_order(**params)
        else:
            print('no need to reset')
            print(f'{self.base_asset}: {current_size} {self.quote_asset}: {current_dols}')

    def build_history(self,reward=None,initial_record=False):
        hist_config=dict(idx = self._idx,
                step = self._step,
                date =pd.Timestamp(datetime.datetime.now()) ,
                position_index =0 if self._position ==0 else self.positions.index(round(self._position,2)),
                position = self._position,
                real_position = self._position,
                portfolio_valuation = self._portfolio.valorisation(self._get_price()),
                portfolio_distribution = self._portfolio.get_portfolio_distribution(),
                reward = reward if reward!=None else self.reward_function(self.historical_info))
        data_dict=self.df.iloc[[self._idx]].to_dict('records')[0]
        hist_config.update(data_dict)
        if not initial_record:
            hist_config={c:hist_config[c] if c in hist_config else None for c in self.historical_info.columns }      
        return hist_config
    
    def _load_history(self,position=None):
        
        self.historical_info = History(max_size=1000)

        history_df=pd.read_sql(f'select * from {self.symbol}_trade_history',self.conn)
        history_df=history_df.tail(len(self.df))
        history=history_df.to_dict('records')
        for i,h in enumerate(history):
            col_list=sorted(h)
            h={c:h[c] for c in col_list}

            if i==0:
                self.historical_info.set(**h)
            else:
                self.historical_info.add(**h)
        
        self._position=position if position!=None else round(self.historical_info["position", -1],2)

    def _save_history(self):
        history_df=pd.DataFrame([self.historical_info[-1]])

        if self._restore_trading==False and self._step==0:
            
            history_df.to_sql(f'{self.symbol}_trade_history',self.conn,if_exists='replace',index=False)
        else:
            history_df.to_sql(f'{self.symbol}_trade_history',self.conn,if_exists='append',index=False)
            
    def reset(self,seed = None, options=None,reset_account=False):
        self._idx=-1
        self._step = 0
        self._limit_orders = {}
        self._position=0
        reward=0
        

        if self._restore_trading:
            self._load_history()
            reward=self.reward_function(self.historical_info)
        if reset_account:
            try:
                self.reset_account()
            except Exception as e:
                print(e)
            
        self._set_df(self.get_data())
        self._portfolio  = TargetPortfolio(
            position = self._position,
            value = self.portfolio_initial_value,
            price = self._get_price()
        )
        
        
        if self._restore_trading:
            position=None
            if reset_account:
                position=0
            self._load_history(position=position)
            hist_config=self.build_history(reward=reward)
            self.historical_info.add(**hist_config)
        else:
            self.historical_info = History(max_size=1000)
            hist_config=self.build_history(reward=reward,initial_record=True)
            self.historical_info.set(**hist_config)
            
        self._save_history()
        
        return self._get_obs(), self.historical_info[-1]
