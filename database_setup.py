import importlib
import click
import asyncio
import traceback
import sys

from cogs.utils.db import Table
from bot import initial_extensions, creds


@click.group(invoke_without_command=True, options_metavar='[options]')
def main():
    pass


@main.group(short_help='database stuff', options_metavar='[options]')
def db():
    pass


@db.command(short_help='initialises the databases for the bot', options_metavar='[options]')
@click.argument('cogs', nargs=-1, metavar='[cogs]')
@click.option('-q', '--quiet', help='less verbose output', is_flag=True)
def init(cogs, quiet):
    """This manages the migrations and database creation system for you."""
    print('ok')
    run = asyncio.get_event_loop().run_until_complete
    try:
        run(Table.create_pool(creds['postgresql']))
    except Exception:
        click.echo(f'Could not create PostgreSQL connection pool.\n{traceback.format_exc()}', err=True)
        return

    if not cogs:
        cogs = initial_extensions
    else:
        cogs = [f'cogs.{e}' if not e.startswith('cogs.') else e for e in cogs]

    for ext in cogs:
        try:
            importlib.import_module(ext)
        except Exception:
            click.echo(f'Could not load {ext}.\n{traceback.format_exc()}', err=True)
            return

    for table in Table.all_tables():
        try:
            created = run(table.create(verbose=not quiet, run_migrations=False))
        except Exception:
            click.echo(f'Could not create {table.__tablename__}.\n{traceback.format_exc()}', err=True)
        else:
            if created:
                click.echo(f'[{table.__module__}] Created {table.__tablename__}.')
            else:
                click.echo(f'[{table.__module__}] No work needed for {table.__tablename__}.')


@db.command(short_help='migrates the databases')
@click.argument('cog', nargs=1, metavar='[cog]')
@click.option('-q', '--quiet', help='less verbose output', is_flag=True)
@click.pass_context
def migrate(ctx, cog, quiet):
    """Update the migration file with the newest schema."""

    if not cog.startswith('cogs.'):
        cog = f'cogs.{cog}'

    try:
        importlib.import_module(cog)
    except Exception:
        click.echo(f'Could not load {ext}.\n{traceback.format_exc()}', err=True)
        return

    def work(table, *, invoked=False):
        try:
            actually_migrated = table.write_migration()
        except RuntimeError as e:
            click.echo(f'Could not migrate {table.__tablename__}: {e}', err=True)
            if not invoked:
                click.confirm('do you want to create the table?', abort=True)
                ctx.invoke(init, cogs=[cog], quiet=quiet)
                work(table, invoked=True)
            sys.exit(-1)
        else:
            if actually_migrated:
                click.echo(f'Successfully updated migrations for {table.__tablename__}.')
            else:
                click.echo(f'Found no changes for {table.__tablename__}.')

    for table in Table.all_tables():
        work(table)

    click.echo(f'Done migrating {cog}.')


if __name__ == '__main__':
    main()