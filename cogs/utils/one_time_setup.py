#Does not close the cursor or
import os
excel_path = os.path.join(os.getcwd(), 'cogs', 'utils', 'Sidekick_Data.xlsx')


async def oneTimeSetup(coc, connection, bot, dbt):
    '''This only needs to be run one time, it'll create all the tables and populate them with values'''
    

    #Create a cursor & define Tag
    cursor = connection
    clanTag = '#P0LYJC8C'

    # #Create a table to store clash tag and discord ID
    # await cursor.execute('Create table Tag_to_ID(Tag VARCHAR(20) PRIMARY KEY,ID VARCHAR(60) NOT NULL)')
    #
    # #Create a table to store tags of last war (tags for current war will be retrived via api and then this table will be updated)
    # await cursor.execute('Create table last_war(Tag VARCHAR(20) PRIMARY KEY)')

    #Read the excel file containing data
    import pandas as pd
    df = pd.read_excel(excel_path)

    #This bit here is gonna look ugly, usually I'd make a seperate function but it's one time only...

    for index, row in df.iterrows():
        Tag = row['Clash Tag']
        ID = row['Discord ID']
        cocplayer = bot.coc.players(Tag).get(bot.creds['coctoken'])

        user_id = ID
        ign = cocplayer['name']
        tag = cocplayer['tag']

        for achievement in cocplayer['achievements']:
            if achievement['name'] == 'Friend in Need':
                don = achievement['value']
                break

        starting_donations = don
        current_donations = don
        difference = dbt

        try:
            clan = cocplayer['clan']['name']
        except KeyError:
            clan = ''

        exempt = False

        query = """INSERT INTO claims (userid, ign, tag, starting_donations, 
                            current_donations, difference, clan, exempt) 
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"""

        await connection.db.execute(query, user_id, ign, tag, starting_donations, current_donations,
                                    difference, clan, exempt)

        # sql = f'''INSERT INTO Tag_to_ID(Tag,ID) VALUES('{Tag}','{ID}')'''
        # await cursor.execute(sql)

    #Cleanup~!
    del df


    #Next, let's populate the 'last_war' table to store values of current war

    #Query to get details for current war
    # currentWar = await coc.clans(clanTag).currentwar().get(coc_token)
    #
    # #Get the list of tags
    # tags = [x['tag'] for x in currentWar['clan']['members']]
    #
    # #populate the table
    # for tag in tags:
    #     sql = f'''INSERT INTO last_war(Tag) VALUES('{tag}')'''
    #     await cursor.execute(sql)

    # cursor.close()
    # connection.commit()

