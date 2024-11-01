

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

ta_functions=['ADL',
                'ADX',
                'AO',
                'APZ',
                'ATR',
                'BASP',
                'BASPN',
                'BBANDS',
                'BBWIDTH',
                'BOP',
                'CCI',
                'CFI',
                'CHAIKIN',
                'CHANDELIER',
                'CMO',
                'COPP',
                'DEMA',
                'DMI',
                'DO',

                'EBBP',
                'EFI',
                'EMA',
                'EMV',
                'ER',
                'FISH',
                'FRAMA',
                'FVE',
                'HMA',
                'ICHIMOKU',
                'IFT_RSI',
                'KC',
                'KST',
                'MACD',
                'MFI',
                'MI',
                'MOBO',
                'MOM',
                'MSD',
                'OBV',
                'PERCENT_B',
                'PIVOT',
                'PIVOT_FIB',
                'PPO',
                'PSAR',
                'PZO',

                'ROC',
                'RSI',
                'SAR',
                'SMA',
                'SMM',
                'SMMA',
                'SQZMI',
                'SSMA',
                'STC',
                'STOCH',
                'STOCHD',
                'STOCHRSI',
                'TEMA',
                'TP',
                'TR',
                'TRIMA',
                'TRIX',
                'TSI',
                'UO',
                'VAMA',
                'VBM',
                'VFI',
                'VORTEX',
                'VPT',
                'VWAP',
                'VW_MACD',
                'VZO',
                'WILLIAMS',
                'WILLIAMS_FRACTAL',
                'WMA',
                'WOBV',
                'WTO',
                'ZLEMA']
def get_ta_funcs():
    return ta_functions