# Does asyncio.Server.wait_closed() wait for a connection that is still open?
import asyncio, sys

async def main():
    async def handler(reader, writer):
        await reader.read()          # keep the connection open until the client closes it
        writer.close()
    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    await asyncio.sleep(0.1)         # let the server accept the connection
    server.close()
    try:
        await asyncio.wait_for(server.wait_closed(), 1.0)
        print(sys.version.split()[0], "wait_closed returned with a connection still open")
    except TimeoutError:
        print(sys.version.split()[0], "wait_closed still waiting after 1 s: it waits for the open connection")
    writer.close()

asyncio.run(main())
