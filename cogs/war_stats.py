''' This file contains 2 helper functions and 1 main driver function which does all calculations'''

#First helper function, This is used to find the TH of a player given his/her clash Tag
def getTownHallLevel(clashTag,currentWar):
    #First we search the enemy clan for tag (Assuming it belongs to enemy clan)
    enemySearch = [x['townhallLevel'] for x in currentWar['opponent']['members'] if x['tag']==clashTag]
    #If it exists, we return TH
    if enemySearch:
        return enemySearch[0]
    else:
        #Else we search and return TH from out clan (i.e the tag belongs to our clan)
        return [x['townhallLevel'] for x in currentWar['clan']['members'] if x['tag']==clashTag][0]

#Second helper function, This is used to calculate how many attacks were defended by base
def getdefenses(defenderTag, currentWar):
    # Get all the attacks on base (returns [('attackerTag',stars)..] list)
    attacksOnBase = [(attack['attackerTag'], attack['stars']) for members in currentWar['opponent']['members'] for
                     attack in members['attacks'] if attack['defenderTag'] == defenderTag]

    # varibles to store corresponding values
    defendedAttacks = 0
    totalAttacks = 0

    for attack in attacksOnBase:
        # Get the attacker tag for every attack
        attackerTag = attack[0]
        # In case the TH of attcker(from enemy clan) and defender(from our clan) are same
        if getTownHallLevel(attackerTag, currentWar) == getTownHallLevel(defenderTag, currentWar):
            # First increase the count of total attacks
            totalAttacks += 1
            # check if it wasn't 3'ed
            if attack[1] != 3:
                # Then increase defended attacks
                defendedAttacks += 1
    # Return the values
    return defendedAttacks, totalAttacks

#Main driver function, calculates all values, updates the db, inserts new values
'''(IT WILL NOT DO ANYTHING IF THE WAR HASN'T ENDED), so make sure this is called after the war has ended and before new war search has begun'''
def calculateWarStats(coc, connection):
    '''Takes in coc client and db connection as arguement, then calculates the stats for current war,
        updates the war_stats table by removing the 20th war and inserting the latest war'''

    # create cursor & define tag
    cursor = connection.cursor()
    clanTag = '#P0LYJC8C'

    # Query to get details for current war
    currentWar = await self.bot.coc.clans(clanTag).currentwar().get(self.bot.coc_token)

    # If war hasn't ended yet don't update or calculate anything
    if currentWar['state'] != 'warEnded':
        return

    # This will store all the rows (Essentially being a list of tuples)
    rows = []

    # Loop over all members of clan and calculate all stats
    for member in currentWar['clan']['members']:

        # Some values which will be used to either calculate stats or be fed directly into database
        playerTownhall = member['townhallLevel']
        attacks = member['attacks']

        # Used to store the successful hits i.e 3stars
        successfulHits = []

        # Loop over every attack by member
        for attack in attacks:
            # Find enemy TH level
            enemyTownhall = getTownHallLevel(attack['defenderTag'], currentWar)

            # Only count attack if either player th = enemy th
            if enemyTownhall == playerTownhall:
                hit = 1 if attack['stars'] == 3 else 0
                successfulHits.append(hit)

        # Get Defenses for the member (Returns defendedAttacks,totalAttacks on base)
        defendedAttacks, totalAttacksOnBase = getdefenses(member['tag'], currentWar)

        # Values to be fed into db
        warNo = 1
        playerName = member['name']
        playerTag = member['tag']
        playerTownhall = str(playerTownhall)

        # calculate hitrate and defenserate respectively
        hr = str(sum(successfulHits)) + '/' + str(len(successfulHits))
        dr = str(defendedAttacks) + '/' + str(totalAttacksOnBase)

        # Save all info into a tuple (Easier to insert into db)
        row = (warNo, playerName, playerTag, playerTownhall, hr, dr)

        # Append row to rows list
        rows.append(row)

    # Finally we'll update the database

    # first we increase the war no for all values in table, since new war has been added
    sql = '''UPDATE war_stats SET war_no = war_no +1;'''
    await ctx.db.execute(sql)

    # Next we'll drop all the rows which have war_no greater than 20
    sql = '''DELETE FROM war_stats WHERE war_no>20;'''
    await ctx.db.execute(sql)

    # Now we just insert all values from rows one by one
    for row in rows:
        sql = f'''INSERT INTO war_stats(war_no,name,tag,th,hitrate,defenserate) VALUES {row};'''
        await ctx.db.execute(sql)

    # Finally close cursor and commit changes
    '''Commenting these for now, idk how ctx.db.execute works, remove if these are not needed'''
    # cursor.close()
    # connection.commit()
