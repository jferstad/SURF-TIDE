#!/usr/bin/env python

import pandas as pd
import numpy as np
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import time 
import glob
import shutil
from datetime import datetime
from datetime import timedelta
import subprocess
import tempfile
import os, sys, json, requests
from rank_patients import rank_the_patients
from rank_patients import add_start_end_day_times
from io import StringIO
from joblib import Parallel, delayed

tick = datetime.now()

td = tempfile.mkdtemp()

dexcom_numbers_file = "dexcom_numbers.xls"

CLINIC_ID = "{You can find this via the Dexcom Clarity web portal}"

weeknum = tick.isocalendar()[1]
weekindex = weeknum % 4 + 1
print("week index: " + str(weekindex))

patient_df = pd.read_excel(dexcom_numbers_file, 
	dtype={
		'Population': object, 'Dexcom_Number': object, 'Name': object,
		'Reviewer': object, 'WeeksToReview': int}).dropna()

# Filter by week number
patient_df = patient_df[(patient_df["WeeksToReview"] == 0) | (patient_df["WeeksToReview"] == weekindex)]
patient_df['Dexcom_Number'] = patient_df['Dexcom_Number'].str.replace('u', '', regex=False)

num_of_patients = len(patient_df.index)
patient_df = patient_df.reset_index()
print("Downloading data for " + str(num_of_patients) + " patients")

### GRAB DEXCOM API TOKEN WITH CLINIC CREDENTIALS

# options = webdriver.ChromeOptions()
# options.add_argument("--headless")
# options.add_argument("--window-size=1920,1080")
# options.add_argument("--disable-gpu")
# driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
# driver.get("https://clarity.dexcom.com/professional/")
# time.sleep(3)
# driver.find_element_by_name("username").send_keys("USERNAME")
# driver.find_element_by_name("password").send_keys("PASSWORD")
# time.sleep(1)
# driver.find_element_by_xpath("//button[text()='Login']").click()
# time.sleep(3)
# api_token_dict = json.loads(driver.execute_script("return window.localStorage['sweetspot-api-token'];"))
# api_token = api_token_dict['token']
# print(api_token)


### CODE TO FETCH FROM FAKE DATA (DISABLE IF USING DEXCOM API)
for index, row in patient_df.iterrows():
	print("Downloading data for patient " + str(index+1) + " of " + str(num_of_patients))
	num = row['Dexcom_Number']

	dl = pd.read_csv(os.path.join("fake_data", "fake_dt_id_u" + num + ".csv"))

	# Remove unneeded columns
	dl = dl.rename(columns={"Timestamp (YYYY-MM-DDThh:mm:ss)": "ts", "Glucose Value (mg/dL)": "bg"})
	dl = dl[["ts", "bg"]]

	# Replace High and Low bg values
	dl['bg'] = dl['bg'].replace(['High'], 400)
	dl['bg'] = dl['bg'].replace(['Low'], 40)

	# Add Name column to download
	dl['patient_id'] = num
	dl['patient_name'] = row['Name']
	dl['population'] = row['Population']
	dl.to_csv(os.path.join(td, "proc_" + num + ".csv"), index = False)


### ITERATE OVER PATIENTS AND DOWNLOAD CGM DATA WITH API

# request_start_date = tick - timedelta(13)
# request_start_date = f"{request_start_date:%Y-%m-%d}"
# request_end_date = tick + timedelta(1)
# request_end_date = f"{request_end_date:%Y-%m-%d}"
# request_data = {
# 	'locale':'en-US',
# 	'units':'mgdl',
# 	"dateInterval":request_start_date+'/'+request_end_date,
# 	'accessToken':api_token}
# print(request_data)

# def grab_patient_data(index, row):
# 	print("Downloading data for patient " + str(index+1) + " of " + str(num_of_patients))
# 	num = row['Dexcom_Number']
# 	api_request_url = 'https://clarity.dexcom.com/api/v1/clinics/{c}/patients/{p}/export'.format(c=CLINIC_ID, p=num)
	
# 	try:
# 		response = requests.post(api_request_url, data=request_data)
# 		dl = pd.read_csv(StringIO(response.text))

# 		# Remove unneeded columns
# 		dl = dl.rename(columns={"Timestamp (YYYY-MM-DDThh:mm:ss)": "ts", "Glucose Value (mg/dL)": "bg"})
# 		dl = dl[["ts", "bg"]]

# 		# Replace High and Low bg values
# 		dl['bg'] = dl['bg'].replace(['High'], 400)
# 		dl['bg'] = dl['bg'].replace(['Low'], 40)

# 		# Add Name column to download
# 		dl['patient_id'] = num
# 		dl['patient_name'] = row['Name']
# 		dl['population'] = row['Reviewer']
# 		dl.to_csv(os.path.join(td, "proc_" + num + ".csv"), index = False)

# 	except Exception as e:
# 		# Create dummy dataframe to note missing data
# 		dl = pd.DataFrame({'ts': [datetime.now().strftime("%Y-%m-%dT%H:%M:%S")], 'bg': [0]})
# 		dl['patient_id'] = num
# 		dl['patient_name'] = row['Name'] + " (MISSING DATA)"
# 		dl['population'] = row['Reviewer']
# 		dl.to_csv(os.path.join(td, "proc_" + num + ".csv"), index = False)
# 		print("SKIPPED PATIENT -- data pull failed")

# Parallel(n_jobs=32)(delayed(grab_patient_data)(index, row) for index, row in patient_df.iterrows())


# Combine data into a single csv and remove temp files
cgmFiles = glob.glob(os.path.join(td, 'proc_*.csv'))
print(cgmFiles)

li = []
for filename in cgmFiles:
	df = pd.read_csv(filename, index_col=None, header=0)
	li.append(df)

comboD = pd.concat(li, axis=0, ignore_index=True)

# Drop duplicate measurements within patient
comboD.drop_duplicates(subset=['ts', 'patient_id'], inplace=True)

# Filter to rows from last two weeks
times_in_data = pd.to_datetime(comboD['ts']).dt.to_period('d').dt.to_timestamp()
#min_time_for_filter = max(times_in_data.dropna()) - timedelta(days=13)
#comboD = comboD[times_in_data >= min_time_for_filter]

# Add indicator for measures in past week and in the week before that
date_one_week_ago = max(times_in_data.dropna()) - timedelta(days=6)
times_in_data = pd.to_datetime(comboD['ts']).dt.to_period('d').dt.to_timestamp() # Round to date
comboD['most_recent_week'] = np.where(times_in_data >= date_one_week_ago, 1, 0)

# add relative week numbers for dash
latest_week_number_in_data = max(times_in_data.dropna()).isocalendar()[1]
comboD = comboD.dropna(subset=['ts'])
comboD['rel_week_num_from_end'] = comboD['ts'].apply(lambda x : (latest_week_number_in_data - pd.to_datetime(x).isocalendar()[1]) % 53)

# Do the rankings
out = rank_the_patients(comboD)

# Add a timestamp at the beginning and end of each day for each patient.
out = add_start_end_day_times(out)

out.to_csv("CGM Dashboard_v3.twb Files/Data/clean_data/cgm_wo_names.csv", index = False)

# comboD.to_csv("comboD.csv", index = False) # DEBUG
#print(td) # DEBUG
shutil.rmtree(td)

if sys.platform == "win32":
	os.startfile("CGM Dashboard_v4.twb")
else:
	subprocess.call(['open', "CGM Dashboard_v4.twb"])

tock = datetime.now() 
diff = tock - tick 
print(diff.total_seconds())
print("DONE")
