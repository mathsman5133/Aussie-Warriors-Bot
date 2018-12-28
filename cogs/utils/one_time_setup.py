#Does not close the cursor or
import os
import csv
excel_path = os.path.join(os.getcwd(), 'cogs', 'utils', 'Sidekick_Data.csv')

async def oneTimeSetup(coc,connection, coc_token):
    '''This only needs to be run one time, it'll create all the tables and populate them with values'''


    #Create a cursor & define Tag
    cursor = connection.cursor()
    clanTag = '#P0LYJC8C'

    # #Create a table to store clash tag and discord ID
    # await cursor.execute('Create table Tag_to_ID(Tag VARCHAR(20) PRIMARY KEY,ID VARCHAR(60) NOT NULL)')
    #
    # #Create a table to store tags of last war (tags for current war will be retrived via api and then this table will be updated)
    # await cursor.execute('Create table last_war(Tag VARCHAR(20) PRIMARY KEY)')

    #Read the excel file containing data
    # import pandas as pd
    # df = pd.read_excel(excel_path)
    #
    # #This bit here is gonna look ugly, usually I'd make a seperate function but it's one time only...
    #
    # for index, row in df.iterrows():
    #with open(excel_path) as csv_file:
    #    csv_reader = csv.reader(csv_file, delimiter=',')
    #    line_count = 0
    #    for row in csv_reader:
    #        if line_count == 0:
    #            line_count += 1
    #            pass
    #        else:
    #            Tag = row['Clash Tag']
    #            ID = row['Discord ID']
    #            sql = f'''INSERT INTO Tag_to_ID(Tag,ID) VALUES('{Tag}','{ID}')'''
    #            await cursor.execute(sql)

    #Cleanup~!
    # del df

    #Next, let's populate the 'last_war' table to store values of current war

    #Query to get details for current war
    #currentWar = await coc.clans(clanTag).currentwar().get(coc_token)

    #Get the list of tags
    #tags = [x['tag'] for x in currentWar['clan']['members']]

    #populate the table
    #for tag in tags:
    #    sql = f'''INSERT INTO last_war(Tag) VALUES('{tag}')'''
    #   await cursor.execute(sql)

    ''' This bit from here on is for stats part, nothing to do with war role'''
    #Create a table to store ('war_no','Name','Tag','TH','Hitrate','Hitrate_%','DefenseRate','DefenseRate_%')
    await cursor.execute('Create table war_stats(war_no smallint NOT NULL,'+
                         'name VARCHAR(40) NOT NULL,'+
                         'tag varchar (20)NOT NULL '+
                         'th VARCHAR (3) NOT NULL '+
                         'hitrate varchar(10) NOT NULL '+
                         'hitrate_per varchar(8) NOT NULL '+
                         'defenserate varchar (10) NOT NULL '+
                         'defenserate_per varchar (8) NOT NULL)')
    cursor.close()
    connection.commit()

