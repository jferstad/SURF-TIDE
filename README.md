# SURF-TIDE


#### Main content

| File                 | Purpose                                                                                                                                                                                                                  | Notes                                                                                                                                                                                                                                                                                                                                                                              |
|----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `get_from_dexcom.py` | Contains code to download CGM trace data from Dexcom Clarity using provider credentials, rank the patients using code in `rank_patients.py` and then opens Tableau `CGM Dashboard_v4.twb` to show the downloaded data.   | It uses the entries in  `dexcom_numbers.xls`  to determine which patients to full data for. The code that connects to Dexcom is commented out and instead the script pulls fake data from the `fake_data` folder. The first time you open the Tableau dashboard, you may have to manually update the location of the downloaded data (in the `CGM Dashboard_v3.twb Files` folder). |
| `R/app.R`              | R Shiny Dashboard. You can run this via RStudio, or open it in your browser here: https://surfcovid19.shinyapps.io/TIDE_git/                                                                                             | You can use the fake CGM data in the `fake_data` folder to populate the dashboard.                                                                                                                                                                                                                                                                                                 |
---------------------

## Screenshots

#### Tableau Dashboard

![Tableau Dashboard Screenshot](screenshots/Tableau.png?raw=true)

#### R Shiny Dashboard

![R Shiny Dashboard Screenshot](screenshots/RShiny.png?raw=true)
