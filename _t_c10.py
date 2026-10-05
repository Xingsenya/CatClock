# -*- coding: utf-8 -*-
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from catclock import quotes as Q

if os.path.exists(Q.QUOTE_PATH):
    os.remove(Q.QUOTE_PATH)
data = Q.load_custom_quotes()
print("loaded file exists:", os.path.exists(Q.QUOTE_PATH))
print("quotes pools:", len(data["quotes"]), "friday:", len(data["friday"]), "weather:", len(data["weather"]))
print("quote at 10:00:", Q.get_quote("work", 10.0, False, None, 0, data))
print("friday 17.6:", Q.get_quote("work", 17.6, True, None, 0, data))
print("weather rain:", Q.get_quote("work", 14.0, False, "rain", 3, data))
print("weather sun hot:", Q.get_quote("work", 14.0, False, "sun", 0, data))

from catclock import data as D
print("santa ext:", D._HAT_EXT.get("santa"), "cny:", D._HAT_EXT.get("cny"))
print("festive now:", Q.festive_hat_now())
print("OK")
