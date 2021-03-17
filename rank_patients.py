import pandas as pd
import numpy as np

K = 20

def rank_the_patients(df):
	
	df_wo_null = df[~df['bg'].isnull()]

	# gen columns for time_worn, in_range, hypo, extreme_hypo
	df_wo_null['in_range'] = np.where((df_wo_null['bg'] <= 180) & (df_wo_null['bg'] >= 70), 1, 0)
	df_wo_null['hypo'] = np.where(df_wo_null['bg'] < 70, 1, 0)
	df_wo_null['extreme_hypo'] = np.where(df_wo_null['bg'] < 54, 1, 0)
	df_wo_null['ts_shift'] = df_wo_null.groupby('patient_id')['ts'].shift()
	df_wo_null['t_diff'] = (pd.to_datetime(df_wo_null['ts']) - pd.to_datetime(df_wo_null['ts_shift'])).dt.total_seconds()

	pat_week_aggs = df_wo_null.groupby(['patient_id', 'most_recent_week']).agg({
	  'bg': 'count',
	  'in_range': 'mean',
	  'hypo': 'mean',
	  'extreme_hypo': 'mean',
	  't_diff': 'median'
	})

	pat_week_aggs['expected_rows'] = (7*24*60*60)/pat_week_aggs['t_diff']
	pat_week_aggs.loc[(pat_week_aggs['t_diff'] > 4000) | pat_week_aggs['t_diff'].isnull(), 'expected_rows'] = (7*24*60*60)/300.0

	pat_week_aggs['time_worn'] = pat_week_aggs['bg'] / pat_week_aggs['expected_rows']
	pat_week_aggs.drop(['bg','t_diff', 'expected_rows'], axis=1, inplace = True)

	# add flags and collapse to patient level
	pat_week_aggs['num_flags'] = \
	  (pat_week_aggs['hypo'] > 0.04).astype(int) + \
	  (pat_week_aggs['extreme_hypo'] > 0.01).astype(int) + \
	  (pat_week_aggs['in_range'] < 0.65).astype(int)

	pat_week_aggs = pat_week_aggs.reset_index()
	pat_current_week = pat_week_aggs[pat_week_aggs['most_recent_week'] == 1]
	pat_prev_week = pat_week_aggs[pat_week_aggs['most_recent_week'] == 0][['patient_id','num_flags']]
	pat_prev_week.rename(columns={"num_flags": "flags_prev_week"}, inplace = True)
	pat_merge = pd.merge(pat_current_week, pat_prev_week, how='outer', on="patient_id")
	pat_merge = pat_merge.fillna({'flags_prev_week': 0})

	# Rank patients
	pat_merge['neg_tir_for_ranking'] = -1*pat_merge['in_range']
	pat_merge["rank"] = pat_merge[["num_flags","neg_tir_for_ranking"]]\
	  .apply(tuple,axis=1)\
	  .rank(method='dense',ascending=False).astype(int)
	pat_merge.drop(['neg_tir_for_ranking'], axis=1, inplace = True)

	pat_merge['review'] = '(0) Error'
	pat_merge.loc[pat_merge['rank'] <= K, 'review'] = '(1) Top ranked'
	pat_merge.loc[(pat_merge['rank'] > K) & (pat_merge['num_flags'] > 0) & (pat_merge['flags_prev_week'] > 0), 'review'] = '(2) Two weeks outside targets'
	pat_merge.loc[(pat_merge['rank'] > K) & ((pat_merge['num_flags'] == 0) | (pat_merge['flags_prev_week'] == 0)), 'review'] = '(3) None'

	# Join the raw data with the ranking
	out = pd.merge(
		df_wo_null[["ts", "bg", "patient_id", "patient_name", "most_recent_week", "rel_week_num_from_end", "population"]],
		pat_merge[['patient_id','review', 'rank', 'time_worn']], 
	    on=['patient_id'])
	return out

# helper function
def cartesian_product_basic(left, right):
    return (
       left.assign(key=1).merge(right.assign(key=1), on='key').drop('key', 1))

# Function to add a timestamp at the beginning and end of each day for each patient.
# This ensures the missing time periods are included in the daily graphs
def add_start_end_day_times(df):

	patients_in_df = df[['patient_id','patient_name','population','review','rank','time_worn']].drop_duplicates()
	times_in_df = df[['ts','most_recent_week','rel_week_num_from_end']]
	times_in_df['dt'] = times_in_df['ts'].str[:10]
	times_in_df['start_ts'] = times_in_df['dt'] + "T00:00:00"
	times_in_df['end_ts'] = times_in_df['dt'] + "T23:59:59"
	start_tses = times_in_df[['most_recent_week','rel_week_num_from_end', 'start_ts']].drop_duplicates()
	start_tses.rename(columns={"start_ts": "ts"}, inplace = True)
	end_tses = times_in_df[['most_recent_week','rel_week_num_from_end', 'end_ts']].drop_duplicates()
	end_tses.rename(columns={"end_ts": "ts"}, inplace = True)
	tses = pd.concat([start_tses, end_tses])

	# cross join patients and time stamps to get all the observations we want to make sure exist in dataset
	needed_obs = cartesian_product_basic(patients_in_df, tses)
	needed_obs['bg'] = None

	# concat needed_obs and df
	new_df = pd.concat([needed_obs, df])
	return new_df


# Test
# df = pd.read_csv("CGM Dashboard_v3.twb Files/Data/clean_data/cgm_wo_names.csv")
# print(rank_the_patients(df))