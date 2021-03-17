##########################################################################################
# Here you can call all the required libraries for your code to run
##########################################################################################

require(shiny)
require(shinyFiles)
require(data.table)
require(DT)
require(lubridate)
require(dplyr)
require(gt)

############################################################

#Define Functions

ExtremeHypo = function(dt, threshold = 54){
  dt <- dt %>% filter(!is.na(glucose))
  N_Ext_Hypo = sum(dt$glucose < threshold, na.rm = T)/length(dt$glucose)
  return(round(100*N_Ext_Hypo, 2))
}

Time_In_Range = function(dt, lower = 70, upper = 180){
  dt <- dt %>% filter(!is.na(glucose))
  TIR = sum(dt$glucose >= lower & dt$glucose <= upper, na.rm=T)/length(dt$glucose)
  return(round(100*TIR, 0))
}

Percent_Below = function(dt, threshold = 70){
  dt <- dt %>% filter(!is.na(glucose))
  PB = sum(dt$glucose < threshold, na.rm = T)/length(dt$glucose)
  return(round(100*PB,0))
}

# for past week
Percent_Worn = function(dt, possible_readings){
  readings = length(is.na(dt$datetime))
  return(round(readings/possible_readings*100, 0))

}

# Define UI for data upload app ----
ui <- fluidPage(

  # App title ----
  titlePanel("CGM Population Report"),

  # Sidebar layout with input and output definitions ----
  sidebarLayout(
    
    # Sidebar panel for inputs ----
    sidebarPanel(

      # Input: Select a file ----
      fileInput("file1", "Choose CSV File(s)",
                multiple = TRUE,
                accept = c("text/csv",
                           "text/comma-separated-values,text/plain",
                           ".csv")),

      # Horizontal line ----
      tags$hr(),
      
      checkboxInput("current", "Use data until last day of data (instead of until last Sunday of data)", TRUE),
      
      width = 3
    ),
    
    # Main panel for displaying outputs ----
    mainPanel(
      
      # Output: Data file ----
      uiOutput("date_range_used"),
      hr(),
      h4("Top 20 patients to review by CGM metrics"),
      dataTableOutput("top"),
      hr(),
      h4("Patients below top 20 but with flags over two weeks"),
      dataTableOutput("twoweek"),
      hr(),
      h4("Patients missing data"),
      dataTableOutput("missingdata"),
      hr(),
      h4("Patients to review if have time, ranked in order of need based on CGM metrics"),
      dataTableOutput("noreview"),
      width = 9
      
    )
    
  )
)

# Define server logic to read selected file ----
server <- function(input, output, session) {
  
  shinyDirChoose(
    input,
    'dir',
    roots = c(home = '~'),
    filetypes = c('', "csv")
  )
  
  # contants
  TOP_K_TO_REVIEW = 20
 
  #thresholds
  EH_threshold = 1
  TIR_threshold = 65
  PB_threshold = 4
  PW_threshold = c(0, 75)
  Change_threshold = 10
  Change_color_threshold = c(-2, 1)

  calculate_table <- function(dts, last_day) {
    for (i in 1:length(dts)){
      
      S1_cgm = dts[[i]]
      
      five_weeks_ago = last_day-5*7*24*60*60
      two_weeks_ago = last_day-2*7*24*60*60
      one_week_ago = last_day-1*7*24*60*60
      S1_cgm_week <- S1_cgm[((datetime >= one_week_ago) & (datetime < last_day))]
      S1_cgm_week_ago <- S1_cgm[((datetime >= two_weeks_ago) & (datetime < one_week_ago))]
      S1_cgm_month <- S1_cgm[((datetime >= five_weeks_ago) & (datetime < one_week_ago))]
      
      # stats for past month
      TIR_month = Time_In_Range(S1_cgm_month)
      
      # stats for this week
      EH = ExtremeHypo(S1_cgm_week)
      TIR = Time_In_Range(S1_cgm_week)
      PB = Percent_Below(S1_cgm_week)
      PW = Percent_Worn(S1_cgm_week, 1*7*24*12)
      TIR.Change = round(TIR - TIR_month, 0)
      num_flags = max(0, (PW < PW_threshold[2]) + (TIR < TIR_threshold) + (EH > EH_threshold) + (PB > PB_threshold))
      tir_change_color = ifelse(TIR < TIR_threshold, -1, 1) + ifelse(TIR.Change < -Change_threshold, -1, ifelse(TIR.Change > Change_threshold, 1, 0))
      
      # stats for past week
      EH_lw = ExtremeHypo(S1_cgm_week_ago)
      TIR_lw = Time_In_Range(S1_cgm_week_ago)
      PB_lw = Percent_Below(S1_cgm_week_ago)
      PW_lw = Percent_Worn(S1_cgm_week_ago, 1*7*24*12)
      num_flags_lw = max(0, (PW_lw < PW_threshold[2]) + (TIR_lw < TIR_threshold) + (EH_lw > EH_threshold) + (PB_lw > PB_threshold), na.rm = TRUE)
      
      output = data.table("Patient" = S1_cgm$Patient[1],
                          "Worn" = PW,
                          "TIR" = TIR,
                          'TIR.Month' = round(TIR_month, 0),
                          "TIR.Change" = TIR.Change,
                          "TBR.54" = EH,
                          "TBR.70" = PB,
                          "num_flags" = num_flags,
                          "tir_change_color" = tir_change_color,
                          "num_flags_last_week" = num_flags_lw
                          )
      
      if (i > 1){
        out = rbind(out, output)
      } else {
        out = output
      }
    }
    
    out = out[order(-num_flags, TIR)]
    out[,rnk:=.I]
    
    # make review decisions
    out[, review := "no_decision"]
    out[rnk <= TOP_K_TO_REVIEW, review := "topK"]
    out[rnk > TOP_K_TO_REVIEW & num_flags*num_flags_last_week > 0, review := "two-weeks-of-flags"]
    out[rnk > TOP_K_TO_REVIEW & num_flags*num_flags_last_week == 0, review := "no"]
    out[Worn == 0, review := "missing_data"]
    out[,rnk:=NULL]
    
    return(out)
  }
  
  load_data <- reactive({
    req(input$file1)
    #go through all the files chosen
    files = input$file1$datapath
    dts = lapply(seq(1,length(files)), function(x) {
      dt = fread(files[x])
      #dt = dt[ `Event Type` == "EGV", c(1,2,8)]
      setnames(dt, c("Timestamp (YYYY-MM-DDThh:mm:ss)" , "Glucose Value (mg/dL)"), c("datetime", "glucose")) 
      dt[,datetime := as.POSIXct(datetime, format = '%Y-%m-%dT%H:%M:%S')]
      dt$glucose = as.numeric(dt$glucose)
      filename = toString(input$file1$name[x])
      dt$Patient = paste(strsplit(filename, "_")[[1]][4], strsplit(filename, "_")[[1]][3])
      return(dt)
    })
    return(dts)
  })
  
  define_end_date <- reactive({
    dt = rbindlist(load_data())
    end_date = floor_date(max(dt$datetime), "day")
    if (input$current) {
      end_date = floor_date(end_date, "day")
    } else {
      end_date = floor_date(end_date, "week")
    }
  })
  
  get_table <- reactive({
    req(input$file1)
    return(calculate_table(load_data(), define_end_date()))
  })
  
  output$date_range_used <- renderUI({
    req(input$file1)
    p(paste("Currently using data until", define_end_date()))
  })
  
  format_dt <- function(dt) {
    #format table for readability
    datatable(dt, 
              options=list(
                dom = 't',
                pageLength=100, 
                columnDefs = list(list(visible=FALSE, targets=c(8,9,10,11)))), 
              colnames=c("Patient", "Worn (%)", "Most Recent Week TIR (%)", "Previous Month TIR (%)", "Change (%)", "< 54 (%)", "< 70 (%)", 
                         "num_flags", "tir_change_color", "num_flags_last_week", "review")) %>%
      formatStyle(
        'TIR',
        backgroundColor = styleInterval(TIR_threshold, c('red', 'none'))) %>%
      formatStyle(
        'TBR.54',
        backgroundColor = styleInterval(EH_threshold, c('none', 'red'))) %>%
      formatStyle(
        'TBR.70',
        backgroundColor = styleInterval(PB_threshold, c('none', 'red'))) %>%
      formatStyle(
        'Worn',
        backgroundColor = styleInterval(PW_threshold, c('yellow', 'red', 'none'))) %>%
      formatStyle(
        'TIR.Change', valueColumns = 'tir_change_color',
        backgroundColor = styleInterval(Change_color_threshold, c('red', 'yellow', 'none')))
    
  }

  output$top <- DT::renderDataTable({
    req(input$file1)
    format_dt(get_table()[review=="topK"])
  })
  
  output$twoweek <- DT::renderDataTable({
    req(input$file1)
    format_dt(get_table()[review=="two-weeks-of-flags"])
  })
  
  output$missingdata <- DT::renderDataTable({
    req(input$file1)
    format_dt(get_table()[review=="missing_data"])
  })
  
  output$noreview <- DT::renderDataTable({
    req(input$file1)
    format_dt(get_table()[review=="no"])
  })
}

# Run the app ----
shinyApp(ui, server)
