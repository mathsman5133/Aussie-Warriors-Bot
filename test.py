import coc
import asyncio

loop = asyncio.get_event_loop()
client = coc.Client(loop, 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6IjNlMzM0ZTE1LWMyNmMtNGVlZi04ZTY5LWIyZmM1OWI1MTExZSIsImlhdCI6MTU1NTY2NzMwNiwic3ViIjoiZGV2ZWxvcGVyL2M3YTNjN2RjLWIxMmYtZTUzZi05NmY4LWNlYjhhNDZiOGMxZSIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjQ5LjE4MC4xMzQuNzYiXSwidHlwZSI6ImNsaWVudCJ9XX0.K1tb_FisGNI1GeQeRKN2U48hErb72rDgv3mrL_dFtJ_nsvKyFApm8jQRKc4gAy0DFDr8OUp3q__Ro3T6CLCsrA',
                    update_tokens=True, email='mathsman5132@gmail.com', password='creepy_crawley')


async def main():
    try:
        await get_some_player('#9OVQLQYCY')
    except coc.Forbidden as e:
        print(e.message, e.reason)
    await get_five_clans('name')
    await client.close()


async def get_some_player(tag):
    player = await client.get_player(tag)

    print(player)


async def get_five_clans(name):
    players = await client.search_clans(name=name, limit=5)
    for n in players:
        print(n, n.tag)


if __name__ == '__main__':
    loop.run_until_complete(main())
