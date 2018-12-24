def getIds(coc, connection)
    '''Takes in the client and connection as arguement, returns tuple of 2 lists (remove,add)'''

    try:
        # Create a cursor & define tag
        cursor = connection.cursor()
        clanTag = '#P0LYJC8C'

        # Query to get details for current war
        currentWar = coc.clans(clanTag).currentwar().get()

        # Get the list of tags
        currentTags = [x['tag'] for x in currentWar['clan']['members']]

        # Get a list of tags from last war
        sql = 'select * from last_war'
        cursor.execute(sql)
        lastTags = [x[0] for x in cursor.fetchall()]

        # Little bit memory waste T_T
        # Create sets from lists (so finding difference is easy)
        current = set(currentTags)
        last = set(lastTags)

        # people who were in last war but are not in current war
        remove = tuple(last - current)

        # people who are in current war but weren't in last
        add = tuple(current - last)

        # now that we have tags, we just need to query table tag_to_id to get corresponding Ids

        # To remove
        sql = f'select ID from tag_to_id where Tag in {remove}'
        cursor.execute(sql)
        idsToRemove = [x[0] for x in cursor.fetchall()]

        # To add
        sql = f'select ID from tag_to_id where Tag in {remove}'
        cursor.execute(sql)
        idsToAdd = [x[0] for x in cursor.fetchall()]

    # In case anything breaks
    except Exception as error:
        print(error)
        # Probably wanna do something here... not sure what tho
        return

    # If nothing goes wrong return lists
    return idsToRemove, idsToAdd