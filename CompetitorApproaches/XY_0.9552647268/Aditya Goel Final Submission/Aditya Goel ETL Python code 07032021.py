# importing packages
import numpy as np
import pandas as pd
import os
import datetime
import time
import warnings

from datetime import datetime, timezone
from difflib import SequenceMatcher

# setting directory and pandas max rows/cols
os.chdir("D:/Technology/Hackathons/Data Engineer Analytics Vidya")
pd.set_option('display.max_rows',None)
pd.set_option('display.max_columns',None)

warnings.filterwarnings("ignore")

# importing data files
userTable = pd.read_csv("userTable.csv")
VisitorLogsData = pd.read_csv("VisitorLogsData.csv")

# cleaning userTable
userTable["Signup Date"] = pd.to_datetime(userTable["Signup Date"])
userTable["year"]= pd.DatetimeIndex(userTable['Signup Date']).year
userTable["month"]= pd.DatetimeIndex(userTable['Signup Date']).month
userTable["day"]= pd.DatetimeIndex(userTable['Signup Date']).day
userTable['UserID'] = userTable['UserID'].str.upper()


# cleaning visitor log
## converting to upper strings
VisitorLogsData['ProductID'] = VisitorLogsData['ProductID'].str.upper()
VisitorLogsData['UserID'] = VisitorLogsData['UserID'].str.upper()
VisitorLogsData['Activity'] = VisitorLogsData['Activity'].str.upper()
VisitorLogsData['Browser'] = VisitorLogsData['Browser'].str.upper()
VisitorLogsData['City'] = VisitorLogsData['City'].str.upper()
VisitorLogsData['OS'] = VisitorLogsData['OS'].str.upper()
VisitorLogsData['Country'] = VisitorLogsData['Country'].str.upper()

## cleaning VisitDateTime - separately for unix vs non-unix dates
VisitorLogsData['date_type_t_f'] = VisitorLogsData['VisitDateTime'].str.isdigit().fillna(False)

df1 = VisitorLogsData[VisitorLogsData['date_type_t_f']==True]
df2 = VisitorLogsData[VisitorLogsData['date_type_t_f']==False]

df1.VisitDateTime = pd.to_numeric(df1.VisitDateTime)
df1['VisitDateTime2'] = (df1.VisitDateTime/1000000)
df1['VisitDateTime2'] = df1['VisitDateTime2'].apply(np.int64)
df1['VisitDateTime'] =  pd.to_datetime(df1['VisitDateTime2'], unit='ms')
df1 = df1.drop(columns = 'VisitDateTime2')

df2.VisitDateTime = pd.to_datetime(df2.VisitDateTime)

## appending the cleaned datetimes dataframes
df3 = df1.append(df2)
df3 = df3.drop(columns = 'date_type_t_f')
df3['date'] = pd.DatetimeIndex(df3.VisitDateTime).date

## missing value treatments / imputations for Activity and ProductID
df3 = df3.sort_values(['UserID','webClientID','VisitDateTime'])

df3['oldProductID'] = df3.groupby(['UserID','date'])['ProductID'].shift(1)
df3['priorProductID'] = df3.groupby(['UserID'])['ProductID'].shift(1)
df3['nextProductID'] = df3.groupby(['UserID'])['ProductID'].shift(-1)

df3['newActivity'] = np.where(df3['ProductID']==df3['oldProductID'],'CLICK','PAGELOAD')
df3['Activity'] = np.where(df3['Activity'].notnull(),df3['Activity'],df3['newActivity'])

df3['newProductID'] = np.where(df3['Activity']=='CLICK',df3['priorProductID'],df3['nextProductID'])
df3['ProductID'] = np.where(df3['ProductID'].notnull(),df3['ProductID'],df3['newProductID'])

df3['priorProductID'] = df3.groupby(['UserID'])['ProductID'].shift(1)
df3['nextProductID'] = df3.groupby(['UserID'])['ProductID'].shift(-1)
df3['newProductID'] = np.where(df3['Activity']=='CLICK',df3['priorProductID'],df3['nextProductID'])
df3['ProductID'] = np.where(df3['ProductID'].notnull(),df3['ProductID'],df3['newProductID'])

df3['ProductID'] = np.where(df3['ProductID'].notnull(),df3['ProductID'],df3['ProductID'].ffill().bfill())

df3['priordate'] = df3.groupby(['UserID'])['date'].shift(1)
df3['nextdate'] = df3.groupby(['UserID'])['date'].shift(-1)
df3 = df3.sort_values(['UserID','webClientID','ProductID'])
df3['VisitDateTime'] = np.where(df3['VisitDateTime'].notnull(),df3['VisitDateTime'],df3['VisitDateTime'].ffill().bfill())

# dropping duplicate records by user/system and time

df3 = df3.drop_duplicates(subset = ['UserID', 'webClientID','VisitDateTime'], keep = 'first').reset_index(drop = True)


# metrics calculation

last_7_days = df3[df3['VisitDateTime']>=(max(df3['VisitDateTime'])-pd.to_timedelta(7, unit='d'))]
last_15_days = df3[df3['VisitDateTime']>=(max(df3['VisitDateTime'])-pd.to_timedelta(15, unit='d'))]

# No_of_days_Visited_7_Days - How many days a user was active on platform in the last 7 days - count distinct visitdatetime by userid when webclientid = 1
no_visit_7d = pd.DataFrame(last_7_days.groupby('UserID').date.nunique())
no_visit_7d = no_visit_7d.reset_index()
no_visit_7d = no_visit_7d.rename(columns = {'date':'No_of_days_Visited_7_Days'})

# Clicks_last_7_days - Count of Clicks in the last 7 days  by the user
click_counts = pd.DataFrame(last_7_days[last_7_days['Activity']=='CLICK'].groupby('UserID').Activity.count())
click_counts = click_counts.reset_index()
click_counts = click_counts.rename(columns = {'Activity':'Clicks_last_7_days'})

# Pageloads_last_7_days - Count of pageloads in the last 7 days  by the user
pageload_counts = pd.DataFrame(last_7_days[last_7_days['Activity']=='PAGELOAD'].groupby('UserID').Activity.count())
pageload_counts = pageload_counts.reset_index()
pageload_counts = pageload_counts.rename(columns = {'Activity':'Pageloads_last_7_days'})

# No_Of_Products_Viewed_15_Days - Number of Products viewed by the user in the last 15 days
no_prod_15d = pd.DataFrame(last_15_days.groupby('UserID').ProductID.nunique())
no_prod_15d = no_prod_15d.reset_index()
no_prod_15d = no_prod_15d.rename(columns = {'ProductID':'No_Of_Products_Viewed_15_Days'})

# Most frequently viewed (page loads) product by the user in the last 15 days. If there are multiple products that have 
# a similar number of page loads then , consider the recent one. If a user has not viewed any product in the last 15 days 
# then put it as Product101. 

most_view_prod_15d = last_15_days[last_15_days['Activity']=='PAGELOAD'].groupby(['UserID','ProductID']).\
                                agg({'Activity':'count','VisitDateTime':'max'})
most_view_prod_15d = most_view_prod_15d.reset_index()

most_view_prod_15d_grp = most_view_prod_15d.sort_values(['Activity','VisitDateTime'], ascending=False).drop_duplicates(['UserID'])
most_view_prod_15d_grp =most_view_prod_15d_grp.sort_values('UserID')

most_view_prod = most_view_prod_15d_grp[['UserID','ProductID']]
most_view_prod = most_view_prod.rename(columns = {'ProductID':'Most_Viewed_product_15_Days'})

#User vintage is today - signup date (Vintage (In Days) of the user as of today)
user_vintage_days = userTable.copy()
user_vintage_days['today'] = pd.to_datetime('2018-05-27',utc=True)
user_vintage_days['User_Vintage'] = (user_vintage_days['today']-user_vintage_days['Signup Date']).dt.days
user_vintage_days= user_vintage_days[['UserID','User_Vintage']]

# Most_Active_OS - Most Frequently used OS by user
most_active_os_data = df3.groupby(['UserID','OS']).\
                                agg({'webClientID':'count',\
                                    'VisitDateTime':'max'})
most_active_os_data = most_active_os_data.sort_values(by = ['UserID']).reset_index()

most_active_os_data_grp = most_active_os_data.sort_values(['webClientID','VisitDateTime'], ascending=False).drop_duplicates(['UserID'])

most_active_os_df = most_active_os_data_grp[['UserID','OS']]
most_active_os_df = most_active_os_df.rename(columns = {'OS':'Most_Active_OS'})
most_active_os_df = most_active_os_df.sort_values('UserID')


# Recently_Viewed_Product - Most recently viewed (page loads) product by the user. If a user has not viewed any product then put it as Product101.

recent_product = df3[(df3['Activity']=='PAGELOAD') & (pd.notnull(df3['ProductID']))]
recent_product = recent_product[['UserID','ProductID','VisitDateTime']]

recent_product_grp = recent_product.sort_values('VisitDateTime', ascending=False).drop_duplicates(['UserID'])
recent_product_grp = recent_product_grp.sort_values('UserID')
recent_product_grp = recent_product_grp[['UserID','ProductID']]
recent_product_grp = recent_product_grp.rename(columns = {'ProductID':'Recently_Viewed_Product'})

# Merging all data

main_data = userTable[['UserID']]

df_join = main_data\
            .merge(no_visit_7d, how='left', on = 'UserID')\
            .merge(no_prod_15d, how='left', on = 'UserID')\
            .merge(user_vintage_days, how='left', on = 'UserID')\
            .merge(most_view_prod, how='left', on = 'UserID')\
            .merge(most_active_os_df, how='left', on = 'UserID')\
            .merge(recent_product_grp, how='left', on = 'UserID')\
            .merge(pageload_counts, how='left', on = 'UserID')\
            .merge(click_counts, how='left', on = 'UserID')

# Missing value treatment and adding Product101
df_join['No_of_days_Visited_7_Days'] = df_join['No_of_days_Visited_7_Days'].replace(np.nan, 0)
df_join['No_Of_Products_Viewed_15_Days'] = df_join['No_Of_Products_Viewed_15_Days'].replace(np.nan, 0)
df_join['User_Vintage'] = df_join['User_Vintage'].replace(np.nan, 0)
df_join['Pageloads_last_7_days'] = df_join['Pageloads_last_7_days'].replace(np.nan, 0)
df_join['Clicks_last_7_days'] = df_join['Clicks_last_7_days'].replace(np.nan, 0)

df_join['Most_Viewed_product_15_Days'] = df_join['Most_Viewed_product_15_Days'].replace(np.nan, 'PRODUCT101')
df_join['Recently_Viewed_Product'] = df_join['Recently_Viewed_Product'].replace(np.nan, 'PRODUCT101')

# changing datatypes to int
df_join['No_of_days_Visited_7_Days'] = df_join['No_of_days_Visited_7_Days'].astype(int)
df_join['No_Of_Products_Viewed_15_Days'] = df_join['No_Of_Products_Viewed_15_Days'].astype(int)
df_join['User_Vintage'] = df_join['User_Vintage'].astype(int)
df_join['Pageloads_last_7_days'] = df_join['Pageloads_last_7_days'].astype(int)
df_join['Clicks_last_7_days'] = df_join['Clicks_last_7_days'].astype(int)

df_join.sort_values('UserID',inplace=True)

# exporting final to csv
df_join.to_csv("aditya_goel_data_engrng_op.csv",index=False)