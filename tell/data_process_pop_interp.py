import glob
import pandas as pd
import numpy as np
import os

import tell.metadata_eia as meta_eia

def fips_pop_yearly(pop_input_dir, start_year, end_year):
    """Read in population data, format columns and return single df for all years
    :param pop_input_dir:                      Directory where county population is stored
    :type pop_input_dir:                       dir
    :param start_year:                         Year to start model ; four digit year (e.g., 1990)
    :type start_year:                          int
    :param end_year:                           Year to start model ; four digit year (e.g., 1990)
    :type end_year:                            int
    :return:                                   Dataframe of valid population data for select timeframe
    """

    # get population from merged mapping data
    df_pop = pd.read_csv(pop_input_dir + '/county_populations_2000_to_2019.csv')

    # loop over years for pop data
    df = pd.DataFrame([])
    for y in range(start_year, end_year + 1):
        # only keep columns that are needed
        key = [f'pop_{y}', 'county_FIPS']

        # change pop yr name for later merging
        df_pop_yr = df_pop[key].copy()

        df_pop_yr['year'] = y
        df_pop_yr.rename(columns={f'pop_{y}': 'population'}, inplace=True)

        # combine all years for one dataset
        df = df.append(df_pop_yr)

    return df


def merge_mapping_data(map_input_dir, pop_input_dir, start_year, end_year):
    """Merge the fips county data and population data from FIPS code
     :param map_input_dir:                      Directory where fips county data is stored
     :type map_input_dir:                       dir
     :param pop_input_dir:                      Directory where county population is stored
     :type pop_input_dir:                       dir
     :param start_year:                         Year to start model ; four digit year (e.g., 1990)
     :type start_year:                          int
     :param end_year:                           Year to start model ; four digit year (e.g., 1990)
     :type end_year:                            int
     :return:                                   Dataframe of population data with FIPS and BA name
     """
    # load FIPS county data for BA number and FIPs code matching for later population sum by BA
    all_files = glob.glob(map_input_dir + "state_and_county_fips_codes.csv")

    list = []

    for filename in all_files:
        df = pd.read_csv(filename, index_col=None, header=0)
        list.append(df)

    frame = pd.concat(list, axis=0, ignore_index=True)
    col_names = ['Year', 'County_FIPS', 'BA_Number']

    # only keep columns that are needed
    frame = frame[col_names].copy()
    frame['BA_Number'] = frame['BA_Number'].fillna(0).astype(np.int64)
    frame['County_FIPS'] = frame['County_FIPS'].fillna(0).astype(np.int64)

    num = frame['BA_Number'].totuple()
    unique_num = np.unique(num).tolist()
    # select for valid BA numbers (from BA metadata)
    metadata_df = metadata_eia([unique_num])


    # merge mapping df to the the metadata
    df_map = frame.merge(metadata, on=['ba_number'])
    df_map.rename(columns={"county_fips": "county_FIPS"}, inplace=True)

    # get sum of population by FIPS and merge to mapping file
    df_pop = fips_pop_yearly(pop_input_dir, start_year, end_year)

    df = pd.merge(df_pop, df_map, how='left', left_on=['county_FIPS', 'year'], right_on=['county_FIPS', 'year'])

    return df


def ba_pop_sum(mapping_input_dir, population_input_dir, start_year, end_year):
    """Sum the population by BA number and year
     :param mapping_input_dir:                  Directory where fips county data is stored
     :type mapping_input_dir:                   dir
     :param population_input_dir:               Directory where county population is stored
     :type population_input_dir:                dir
     :param start_year:                         Year to start model ; four digit year (e.g., 1990)
     :type start_year:                          int
     :param end_year:                           Year to start model ; four digit year (e.g., 1990)
     :type end_year:                            int
     :return:                                   Dataframe of total population by BA name and year
     """
    # get population from merged mapping data
    df_pop = merge_mapping_data(mapping_input_dir, population_input_dir, start_year, end_year)

    # loop over years to sum population by year
        # sum population by BA
    df = df_pop.groupby(['BA_Short_Name', 'year'])['population'].sum().reset_index()

    return df


def ba_pop_interpolate(mapping_input_dir, population_input_dir, output_dir, start_year, end_year):
    """Interpolate the population from yearly to hourly timeseries to match EIA 930 hourly data
     :param mapping_input_dir:                  Directory where fips county data is stored
     :type mapping_input_dir:                   dir
     :param population_input_dir:               Directory where county population is stored
     :type population_input_dir:                dir
     :param output_dir:                         Directory where to store the hourly population data
     :type output_dir:                          dir
     :param start_year:                         Year to start model ; four digit year (e.g., 1990)
     :type start_year:                          int
     :param end_year:                           Year to start model ; four digit year (e.g., 1990)
     :type end_year:                            int
     :return:                                   Dataframe of hourly population timeseries for each BA name
     """
    df = ba_pop_sum(mapping_input_dir, population_input_dir, start_year, end_year)
    pd.to_datetime(df['year'], format='%Y')
    df.rename(columns={"population": "pop"}, inplace=True)
    df.rename(columns={'BA_Short_Name': 'name'}, inplace=True)
    # Reshape
    df = df.pivot(index='year', columns='name', values='pop')

    # Build an hourly DatetimeIndex
    idx = pd.date_range(start=f'{start_year}-01-01', end=f'{end_year}-12-31', freq='H')

    # Reindex and interpolate with cubicspline as an example
    res = df.reindex(idx).interpolate(method='linear')

    res.to_csv(os.path.join(output_dir, 'hourly_population.csv'), index=False, header=True)

    return res


