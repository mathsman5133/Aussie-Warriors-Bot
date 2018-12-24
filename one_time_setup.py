#Does not close the cursor or 
def oneTimeSetup(coc,connection):
    '''This only needs to be run one time, it'll create all the tables and populate them with values'''
    
    try:
        
        #Create a cursor & define Tag
        cursor = connection.cursor()
        clanTag = '#P0LYJC8C'

        #Create a table to store clash tag and discord ID
        cursor.execute('Create table Tag_to_ID(Tag VARCHAR(20) PRIMARY KEY,ID VARCHAR(60) NOT NULL)')

        #Create a table to store tags of last war (tags for current war will be retrived via api and then this table will be updated)
        cursor.execute('Create table last_war(Tag VARCHAR(20) PRIMARY KEY)')

        #Read the excel file containing data
        df = pd.read_excel('Sidekick Data.xlsx')

        #This bit here is gonna look ugly, usually I'd make a seperate function but it's one time only...

        for index,row in df.iterrows():
            Tag = row['Clash Tag']
            ID = row['Discord ID']
            sql = f'''INSERT INTO Tag_to_ID(Tag,ID) VALUES('{Tag}','{ID}')'''
            cursor.execute(sql)
        
        #Cleanup~!
        del df
        
        #Next, let's populate the 'last_war' table to store values of current war
        
        #Query to get details for current war
        currentWar = coc.clans(clanTag).currentwar().get()
        
        #Get the list of tags
        tags = [x['tag'] for x in currentWar['clan']['members']]
        
        #populate the table
        for tag in tags:
            sql = f'''INSERT INTO last_war(Tag) VALUES('{tag}')'''
            cursor.execute(sql)
        
        cursor.close()
        connection.commit()
    except Exception as error:
        print(error)