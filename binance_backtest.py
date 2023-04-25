from binance import Client
from datetime import datetime
import pandas as pd
from binance.spot import Spot

## remove "#" and put in api key from binance to run
# api_key = ""
# api_secret = ""
client = Client(api_key, api_secret)

# CHECK THIS VALUE BEFORE RUN THE MODEL ** #
coin = "AAVEUSDT" 
cs_interval = "1h" #1h
num_past_cs = 1000 # max is 1000

# variable to be calibrated
bottom_outlier = 0.10
top_adjusted_lower = 0.30 #30 is conservative
top_adjusted_upper = 0.35

# constant variables
date_found = []
candlestick_index = []

def get_candlestick_data(symbol, timeframe, qty):
    """ pull data from api and stored in a dictionary, then append to an array. """

    # Retrieve the raw data
    raw_data = Spot().klines(symbol=symbol, interval=timeframe, limit=qty)

    converted_data = []
    for candle in raw_data:
        converted_candle = {
            'time': candle[0],
            'open': float(candle[1]),
            'high': float(candle[2]),
            'low': float(candle[3]),
            'close': float(candle[4]),
            'volume': float(candle[5]),
            'close_time': candle[6],
            'quote_asset_volume': float(candle[7]),
            'number_of_trades': int(candle[8]),
            'taker_buy_base_asset_volume': float(candle[9]),
            'taker_buy_quote_asset_volume': float(candle[10])
        }
        
        converted_data.append(converted_candle)
    
    return converted_data

# function
def green_pattern(klines):
    """ looking for green candle sticks with the spcified pattern. """

    count = 0
    for k in klines:
        open = k["open"]
        high = k["high"]
        low = k["low"]
        close = k["close"]
        time = datetime.fromtimestamp(int(k["time"])/1000)

        lower_bound  = top_adjusted_lower * (high - open)
        upper_bound = top_adjusted_upper * (high - open)

        # set condition
        cond_1 = (close > open) # confirm green candlestick
        cond_2 = (((high - close) >= lower_bound) & ((high - close) <= upper_bound)) # check line prop
        cond_3 = (open - low <= bottom_outlier * (close - open)) # check bottom outlier

        if(cond_1 & cond_2 & cond_3):
            print("FOUND")
            print(time)
            count += 1
            date_found.append(time)
            candlestick_index.append(list(klines).index(k))

        else:
            print("-")
    print(f"total: {count} times")
    print(f"candlstick index: {candlestick_index}")
    print(f"{date_found}\n")

def write_patternlog():
    """ write trade log in txt file. """

    with open('pattern_found_log.txt', 'w') as f:
        for line in date_found:
            f.write(str(line))
            f.write('\n')

def ema(symbol, timeframe, ema_size):
    raw_data = get_candlestick_data(symbol=symbol, timeframe=timeframe, qty=num_past_cs)
    # Convert into Dataframe
    dataframe = pd.DataFrame(raw_data)
    # Create column string
    ema_name = "ema_" + str(ema_size)
    # Create the multiplier
    multiplier = 2/(ema_size + 1)
    # Calculate the initial value (SMA)
    # pandas.set_option('display.max_columns', None) # <- use this to show all columns
    # pandas.set_option('display.max_rows', None) # <- use this to show all the rows
    initial_mean = dataframe['close'].head(ema_size).mean()

    # Iterate through Dataframe
    for i in range(len(dataframe)):
        if i == ema_size:
            dataframe.loc[i, ema_name] = initial_mean
        elif i > ema_size:
            ema_value = dataframe.loc[i, 'close'] * multiplier + dataframe.loc[i-1, ema_name]*(1-multiplier)
            dataframe.loc[i, ema_name] = ema_value
        else:
            dataframe.loc[i, ema_name] = 0.00
    # print(dataframe) # <- use this to print the dataframe if you want to inspect
    return dataframe

def test_buy(klines):
    """ fake buy and evalute the result. 
    f: pattern founded candlestick
    c: current candlestick  """
    
    win = 0
    lost = 0
    under_ema = 0

    # set variables
    for i in candlestick_index:
        print("start")
        cs_index = 0
        close_f = klines[i]["close"]
        open_f = klines[i]["open"]
        buy_price = close_f
        sell_price = buy_price + (close_f - open_f)
        stop_loss = open_f

        # next candlestick 
        low_c = klines[i + 1]["low"]
        high_c = klines[i + 1]["high"]

        print(f"pattern found at: {datetime.fromtimestamp(klines[i]['time']/1000)}")
        print(f"sell_price: {sell_price}")
        print(f"stop loss: {stop_loss}")
        print(f"low_c: {low_c}")
        print(f"high_c: {high_c}")


        # find ema 200 value
        ema_df_new = ema(coin, cs_interval, 200)
        bool_df = ema_df_new[:]["time"].astype("int") == int(klines[i]["time"])
        ema_200 = ema_df_new["ema_200"][bool_df].values[0]
        print(f"ema_200: {ema_200}")

        # only if ema_200 above ema_200
        if(open_f > ema_200):

            while(stop_loss < low_c):
                print(f"check: {datetime.fromtimestamp(klines[i + 1 + cs_index]['time']/1000)}")

                if(sell_price <= high_c):
                    win += 1
                    print(f"Profit earned, win +1 at {datetime.fromtimestamp(klines[i + 1 + cs_index]['time']/1000)}")
                    print(f"profit at {round((sell_price - buy_price) * 100 / buy_price, 2)} %")
                    print("end")
                    break
                else:
                    cs_index += 1
                    low_c = klines[i + 1 + cs_index]["low"]
                    high_c = klines[i + 1 + cs_index]["high"]
                    continue
            
            if(stop_loss >= low_c):
                lost += 1
                print("Fail to make a profit")
        else:
            under_ema += 1
            print("under ema200")

        print("\n")

    print(f"win: {win}")
    print(f"lost: {lost}")
    print(f"total candlesticks: {len(candlestick_index)}")
    print(f"candlesticks under ema 200: {under_ema}")
    print(f"win rate: {round((win*100 / (win + lost)), 2)} %")


    
## work starts here - call function
candlestick_data = get_candlestick_data(coin, cs_interval, num_past_cs)
green_pattern(candlestick_data)
write_patternlog()
test_buy(candlestick_data)
