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
import os
import sys
from rank_patients import rank_the_patients
from rank_patients import add_start_end_day_times

tick = datetime.now()

td = tempfile.mkdtemp()

# function to take care of downloading file
def enable_download_headless(browser,download_dir):
	browser.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
	params = {
		'cmd':'Page.setDownloadBehavior',
		'params': {
			'behavior': 'allow', 
			'downloadPath': td
		}
	}
	browser.execute("send_command", params)

if sys.argv[1] == "test":
	dexcom_numbers_file = "dexcom_numbers_test.xls"
	reviewer = sys.argv[2]
else:
	dexcom_numbers_file = "dexcom_numbers.xls"
	reviewer = sys.argv[1]

print("Fetching patients for " + reviewer)	
weeknum = tick.isocalendar()[1]
weekindex = weeknum % 4 + 1
print("week index: " + str(weekindex))

patient_df = pd.read_excel(dexcom_numbers_file, 
	dtype={
		'Population': object, 'Dexcom_Number': object, 'Name': object,
		'Reviewer': object, 'WeeksToReview': int}).dropna()

# Filter by reviewer and week number
patient_df = patient_df[patient_df["Reviewer"] == reviewer]
patient_df = patient_df[(patient_df["WeeksToReview"] == 0) | (patient_df["WeeksToReview"] == weekindex)]
patient_df['Dexcom_Number'] = patient_df['Dexcom_Number'].str.replace('u', '', regex=False)

num_of_patients = len(patient_df.index)
patient_df = patient_df.reset_index()
print("Downloading data for " + str(num_of_patients) + " patients")


# LOGGING INTO DEXCOM
# options = webdriver.ChromeOptions()
# options.add_experimental_option("prefs", {
#   "download.default_directory": td,
#   "download.prompt_for_download": False,
#   "download.directory_upgrade": True,
#   "safebrowsing.enabled": True
# })
# options.add_argument("download.default_directory=" + td)
# options.add_argument("--start-maximized")

# driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
# driver.get("https://clarity.dexcom.com/professional/")
# time.sleep(3)
# htmlSource = driver.page_source

# driver.find_element_by_name("username").send_keys("USERNAME")
# driver.find_element_by_name("password").send_keys("PASSWORD")
# time.sleep(1)

# driver.find_element_by_xpath("//button[text()='Login']").click()

# time.sleep(3)

# function to handle setting up headless download
# enable_download_headless(driver, td)

# method to get the downloaded file name
def getDownLoadedFileName(waitTime):
	driver.execute_script("window.open()")
	# switch to new tab
	driver.switch_to.window(driver.window_handles[-1])
	# navigate to chrome downloads
	driver.get('chrome://downloads')
	# define the endTime
	endTime = time.time()+waitTime
	while True:
		try:
			# get downloaded percentage
			downloadPercentage = driver.execute_script(
				"return document.querySelector('downloads-manager').shadowRoot.querySelector('#downloadsList downloads-item').shadowRoot.querySelector('#progress').value")
			# check if downloadPercentage is 100 (otherwise the script will keep waiting)
			if downloadPercentage == 100:
				# return the file name once the download is completed
				toreturn = driver.execute_script("return document.querySelector('downloads-manager').shadowRoot.querySelector('#downloadsList downloads-item').shadowRoot.querySelector('div#content  #file-link').text")
				driver.execute_script("window.close()")
				return toreturn
		except Exception as e:
			#print(e)
			toreturn = driver.execute_script("return document.querySelector('downloads-manager').shadowRoot.querySelector('#downloadsList downloads-item').shadowRoot.querySelector('div#content  #file-link').text")
			driver.execute_script("window.close()")
			return toreturn
			#pass
		time.sleep(1)
		if time.time() > endTime:
			toreturn = driver.execute_script("return document.querySelector('downloads-manager').shadowRoot.querySelector('#downloadsList downloads-item').shadowRoot.querySelector('div#content  #file-link').text")
			driver.execute_script("window.close()")
			return toreturn
			#break



# CODE TO FETCH FROM Fake Data
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

# CODE TO FETCH FROM DEXCOM 
# last_downloaded_file = ''
# for index, row in patient_df.iterrows():
# 	print("Downloading data for patient " + str(index+1) + " of " + str(num_of_patients))
# 	num = row['Dexcom_Number']
# 	max_attempts_per_patient = 10
# 	attempt = 0
# 	driver.switch_to.window(driver.window_handles[0])
# 	driver.get("https://clarity.dexcom.com/professional/patients/" + num + "/export")
# 	while (True):
# 		attempt = attempt + 1
# 		try:
# 			time.sleep(1)
# 			driver.find_element_by_name("submitExport").click()
# 			fn = getDownLoadedFileName(3)
# 			if fn == last_downloaded_file:
# 				raise Error('No New File Downloaded; Retrying...')
# 			else:
# 				last_downloaded_file = fn

# 			dl = pd.read_csv(os.path.join(td, fn))

# 			# Remove unneeded columns
# 			dl = dl.rename(columns={"Timestamp (YYYY-MM-DDThh:mm:ss)": "ts", "Glucose Value (mg/dL)": "bg"})
# 			dl = dl[["ts", "bg"]]

# 			# Replace High and Low bg values
# 			dl['bg'] = dl['bg'].replace(['High'], 400)
# 			dl['bg'] = dl['bg'].replace(['Low'], 40)

# 			# Add Name column to download
# 			dl['patient_id'] = num
# 			dl['patient_name'] = row['Name']
# 			dl['population'] = row['Population']
# 			dl.to_csv(os.path.join(td, "proc_" + num + ".csv"), index = False)

# 			break
# 		except Exception as e:
# 			if attempt==max_attempts_per_patient//2:
# 				driver.get("https://clarity.dexcom.com/professional/patients/" + num + "/export")

# 			if attempt>=max_attempts_per_patient:
# 				# Create dummy dataframe to note missing data
# 				dl = pd.DataFrame({'ts': [datetime.now().strftime("%Y-%m-%dT%H:%M:%S")], 'bg': [0]})
# 				dl['patient_id'] = num
# 				dl['patient_name'] = row['Name'] + " (MISSING DATA)"
# 				dl['population'] = row['Population']
# 				dl.to_csv(os.path.join(td, "proc_" + num + ".csv"), index = False)
# 				print("SKIPPING PATIENT -- reached max attempts")
# 				break
# driver.quit()


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