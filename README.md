# Aussie-Warriors-Bot


## Running

Many of the commands and features of this bot have been hardcoded to work with both the Aussie Warriors server and the corresponding clash of clans clan. 

However, if you wish to run an instance of this bot the installation steps are as follows:

1. **Get Python3.6 or higher**

Many commands make use of f-strings. This is an amazing feature for versions of python > 3.6

2. **Install dependencies**

Do this with `pip install -U -r requirements.txt` while in the main directory

3. **Create a database in PostgreSQL**
Once you have installed postgres and the `psql` tool, type the following in psql:
```sql
CREATE ROLE awbot WITH LOGIN PASSWORD 'yourpwd';
CREATE DATABASE awbot OWNER awbot;
```

4. **Creating a creds file**
You will need to create a `creds.json` file in the main directory, containing the following:
```py
{
  "coctoken": "" # your Clash of Clans API token from https://developer.clashofclans.com/
  "bottoken": "" # your discord bot's token from https://discordapp.com/developers/applications/
  "postgresql": "postgresql://user:password@host/database" # your postgres info from above: hint host most likely will be "localhost:5432"
}
```

5. **Creating tables and setup of the database**

In the main directory, run the script to setup the database by doing: `python3.6 database_setup.py db init`

6. **Run the bot**

In the main directory, run `bot.py` by doing `python3.6 bot.py`

