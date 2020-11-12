#!/usr/bin/env python3
import click
import requests
import requests.exceptions as reqerrors
import logging
from pathlib import Path
import os
import json
from pprint import pprint
from tabulate import tabulate
import yaml
#from click_option_group import optgroup, MutuallyExclusiveOptionGroup

def create_config_dir():
    home = Path(os.getenv('HOME'))
    Path.mkdir(home / '.config', exist_ok=True)
    synadm_config = home / '.config'
    return synadm_config

def create_data_dir():
    home = Path(os.getenv('HOME'))
    Path.mkdir(home / '.local' / 'share' / 'synadm', parents=True, exist_ok=True)
    synadm_data = home / '.local' / 'share' / 'synadm'
    return synadm_data

def logger_init():
    synadm_data = create_data_dir()
    debug_log = synadm_data / "debug.log"

    log = logging.getLogger('synadm')
    log.setLevel(logging.DEBUG) # level of logger itself
    f_handle = logging.FileHandler(debug_log, encoding='utf-8') # create file handler
    f_handle.setLevel(logging.DEBUG) # which logs even debug messages
    c_handle = logging.StreamHandler() # console handler with a higher log level
    c_handle.setLevel(logging.WARNING) # level of the console handler
    # create formatters and add it to the handlers
    f_form = logging.Formatter('%(asctime)s %(name)-8s %(levelname)-7s %(message)s',
             datefmt='%Y-%m-%d %H:%M:%S')
    c_form = logging.Formatter('%(levelname)-5s %(message)s')
    c_handle.setFormatter(c_form)
    f_handle.setFormatter(f_form)
    log.addHandler(c_handle) # add the handlers to logger
    log.addHandler(f_handle)
    return log

class Synapse_admin (object):
    def __init__(self, user, token, base_url):
        self.user = user
        self.token = token
        self.base_url = base_url.strip('/')

    def _get(self, urlpart):
        headers={'Accept': 'application/json', 'Authorization': 'Bearer ' + self.token }
        url=f'{self.base_url}/_synapse/admin/{urlpart}'
        log.info('_get url: {}\n'.format(url))
        try:
            resp = requests.get(url, headers=headers, timeout=7)
            resp.raise_for_status()
            if resp.ok:
                _json = json.loads(resp.content)
                return _json
            else:
                log.warning("No valid response from Synapse. Returning None.")
                return None
        except reqerrors.HTTPError as errh:
            log.error("HTTPError: %s\n", errh)
            #if "Not found" in errh.response.text:
            #    log.warning("AcousticBrainz doesn't have this recording yet. Consider submitting it!")
            return None
        except reqerrors.ConnectionError as errc:
            log.error("ConnectionError: %s\n", errc)
            return None
        except reqerrors.Timeout as errt:
            log.error("Timeout: %s\n", errt)
            return None
        except reqerrors.RequestException as erre:
            log.error("RequestException: %s\n", erre)
            return None

    def _post(self, urlpart, post_data, log_post_data=True):
        headers={'Accept': 'application/json', 'Authorization': 'Bearer ' + self.token }
        url=f'{self.base_url}/_synapse/admin/{urlpart}'
        log.info('_post url: {}\n'.format(url))
        if log_post_data:
            log.info('_post data: {}\n'.format(post_data))
        try:
            resp = requests.post(url, headers=headers, timeout=7, data=post_data)
            resp.raise_for_status()
            if resp.ok:
                _json = json.loads(resp.content)
                return _json
            else:
                log.warning("No valid response from Synapse. Returning None.")
                return None
        except reqerrors.HTTPError as errh:
            log.error("HTTPError: %s\n", errh)
            return None
        except reqerrors.ConnectionError as errc:
            log.error("ConnectionError: %s\n", errc)
            return None
        except reqerrors.Timeout as errt:
            log.error("Timeout: %s\n", errt)
            return None
        except reqerrors.RequestException as erre:
            log.error("RequestException: %s\n", erre)
            return None

    def user_list(self, _from=0, _limit=100, _guests=False, _deactivated=False,
          _name=None, _user_id=None): # if --options missing they are None too, let's stick with that.
        _deactivated_s = 'true' if _deactivated else 'false'
        _guests_s = 'true' if _guests else 'false'
        urlpart = f'v2/users?from={_from}&limit={_limit}&guests={_guests_s}&deactivated={_deactivated_s}'
        # optional filters
        if _name:
            urlpart+= f'&name={_name}'
        elif _user_id:
            urlpart+= f'&user_id={_user_id}'
        return self._get(urlpart)

    def user_membership(self, user_id):
        urlpart = f'v1/users/{user_id}/joined_rooms'
        return self._get(urlpart)

    def user_deactivate(self, user_id, gdpr_erase):
        urlpart = f'v1/deactivate/{user_id}'
        data = '{"erase": true}' if gdpr_erase else {}
        return self._post(urlpart, data)

    def user_password(self, user_id, password, no_logout):
        urlpart = f'v1/reset_password/{user_id}'
        data = {"new_password": password}
        if no_logout:
            data.update({"logout_devices": no_logout})
        json_data = json.dumps(data)
        return self._post(urlpart, json_data, log_post_data=False)

    def room_list(self, _from, limit, name, order_by, reverse):
        urlpart = f'v1/rooms?from={_from}&limit={limit}'
        if name:
            urlpart+= f'&search_term={name}'
        if order_by:
            urlpart+= f'&order_by={order_by}'
        if reverse:
            urlpart+= f'&dir=b'
        return self._get(urlpart)

    def room_details(self, room_id):
        urlpart = f'v1/rooms/{room_id}'
        return self._get(urlpart)

    def room_members(self, room_id):
        urlpart = f'v1/rooms/{room_id}/members'
        return self._get(urlpart)

    def room_delete(self, room_id, new_room_user_id, room_name, message,
          block, no_purge):
        urlpart = f'v1/rooms/{room_id}/delete'
        purge = False if no_purge else True
        data = {
            "block": block, # data with proper defaults from cli
            "purge": purge  # should go here
        }
        # everything else is optional and shouldn't even exist in post body
        if new_room_user_id:
            data.update({"new_room_user_id": new_room_user_id})
        if room_name:
            data.update({"room_name": room_name})
        if message:
            data.update({"message": message})
        json_data = json.dumps(data)
        return self._post(urlpart, json_data)

    def version(self):
        urlpart = f'v1/server_version'
        return self._get(urlpart)

def modify_usage_error(main_command):
    '''a method to append the help menu to an usage error
    :param main_command: top-level group or command object constructed by click wrapper
    '''
    from click._compat import get_text_stderr
    from click.utils import echo
    def show(self, file=None):
        import sys
        if file is None:
            file = get_text_stderr()
        color = None
        if self.ctx is not None:
            color = self.ctx.color
            echo(self.ctx.get_usage() + '\n', file=file, color=color)
        echo('Error: %s\n' % self.format_message(), file=file, color=color)
        sys.argv = [sys.argv[0]]
        main_command()

    click.exceptions.UsageError.show = show

def get_table(data, listify=False):
    '''expects lists of dicts, fetches header information from first list element
       and saves as a dict (tabulate expects headers arg as dict)
       then uses tabulate to return a pretty printed tables. The listify argument is used
       to wrap very simple "one-dimensional" API responses into a list so tabulate accepts it.'''

    data_list = []
    if listify == False:
        data_list = data
        log.debug('get_table using data as is. Got this: {}'.format(data_list))
    else:
        data_list.append(data)
        log.debug('get_table listified data. Now looks like this: {}'.format(data_list))

    headers_dict = {}
    for header in data_list[0]:
        headers_dict.update({header: header})
    return tabulate(data_list, tablefmt="simple",
          headers=headers_dict)

class Config(object):
    def __init__(self, config_yaml):
        self.config_yaml = os.path.expanduser(config_yaml)
        self.incomplete = False # save weather reconfiguration is necessary
        try:
            conf = self._read_yaml(self.config_yaml)
        except IOError:
            log.debug('No configuration file found, creating empty one.\n')
            Path(self.config_yaml).touch()
            conf = self._read_yaml(self.config_yaml)
        log.debug("Successfully read configuration from {}\n".format(
              self.config_yaml))

        self.user = self._get_config_entry(conf, 'user')
        self.token = self._get_config_entry(conf, 'token')
        self.base_url = self._get_config_entry(conf, 'base_url')

    def _get_config_entry(self, conf_dict, yaml_key, default=''):
        try:
            if conf_dict[yaml_key] == '':
                value = default
                log.warning('Empty entry in configuration file: "{}"'.format(yaml_key))
                self.incomplete = True
            else:
                value = conf_dict[yaml_key]
                log.debug('Configuration entry "{}": {}'.format(yaml_key,
                      conf_dict[yaml_key]))
        except KeyError:
            value = default
            log.warning('Missing entry in configuration file: "{}"'.format(yaml_key))
            self.incomplete = True
        return value

    def write(self, config_values):
        click.echo('Writing configuration to {}'.format(
              self.config_yaml))
        self._write_yaml(config_values)
        click.echo('Done.')

    def _read_yaml(self, yamlfile):
        """expects path/file"""
        try:
            with open(str(yamlfile), "r") as fyamlfile:
                return yaml.load(fyamlfile, Loader=yaml.SafeLoader)
        except IOError as errio:
            log.error("Can't find %s.", yamlfile)
            raise errio
            #raise SystemExit(3)
            #return False
        except yaml.parser.ParserError as errparse:
            log.error("ParserError in %s.", yamlfile)
            #raise errparse
            raise SystemExit(3)
        except yaml.scanner.ScannerError as errscan:
            log.error("ScannerError in %s.", yamlfile)
            #raise errscan
            raise SystemExit(3)
        except Exception as err:
            log.error(" trying to load %s.", yamlfile)
            raise err
            #raise SystemExit(3)

    def _write_yaml(self, data):
        """data expects dict, self.config_yaml expects path/file"""
        try:
            with open(self.config_yaml, "w") as fconfig_yaml:
                yaml.dump(data, fconfig_yaml, default_flow_style=False,
                                 allow_unicode=True)
                return True
        except IOError as errio:
            log.error("IOError: could not write file %s \n\n", self.config_yaml)
            raise errio
        except Exception as err:
            log.error(" trying to write %s \n\n", self.config_yaml)
            raise err
            raise SystemExit(2)



# handle logging and configuration prerequisites
log = logger_init()
create_config_dir()
# change default help options
cont_set = dict(help_option_names=['-h', '--help'])
#usage: @click.command(context_settings=cont_set)

#############################################
### main synadm command group starts here ###
#############################################
@click.group(invoke_without_command=False, context_settings=cont_set)
@click.option('--verbose', '-v', count=True, default=False,
      help="enable INFO (-v) or DEBUG (-vv) logging on console")
@click.option('--raw', '-r', is_flag=True, default=False,
      help="print raw json data (no tables)")
@click.option('--config-file', '-c', type=click.Path(), default='~/.config/synadm.yaml',
      help="configuration file path", show_default=True)
@click.pass_context
def synadm(ctx, verbose, raw, config_file):
    def _eventually_run_config():
        if ctx.invoked_subcommand != 'config':
            ctx.invoke(config)
            click.echo("Now try running your command again!")
            raise SystemExit(1)
        return None # do nothing if it's config command already

    if verbose == 1:
        log.handlers[0].setLevel(logging.INFO) # set cli handler to INFO,
    elif verbose > 1:
        log.handlers[0].setLevel(logging.DEBUG) # or to DEBUG level

    configuration = Config(config_file)
    ctx.obj = {
        'config': configuration,
        'raw': raw,
    }
    log.debug("ctx.obj: {}\n".format(ctx.obj))

    if configuration.incomplete:
        _eventually_run_config()


### the config command starts here ###
@synadm.command(context_settings=cont_set)
@click.option('--user', '-u', type=str, default='admin',
    help="admin user for accessing the Synapse admin API's",)
@click.option('--token', '-t', type=str,
    help="admin user's access token for the Synapse admin API's",)
@click.option('--base-url', '-b', type=str, default='http://localhost:8008',
    help="""the base URL Synapse is running on. Typically this is
    https://localhost:8008 or https://localhost:8448. If Synapse is
    configured to expose its admin API's to the outside world it could also be
    https://example.org:8448""")
@click.pass_context
def config(ctx, user, token, base_url):
    """modify synadm's configuration. configuration details are asked
    interactively but can also be provided using options:"""
    click.echo('Running configurator...')
    configuration = ctx.obj['config']
    # get defaults for prompts from either config file or commandline
    user_default = configuration.user if configuration.user else user
    token_default = configuration.token if configuration.token else token
    base_url_default = configuration.base_url if configuration.base_url else base_url
    api_user = click.prompt("Synapse admin user name", default=user_default)
    api_token = click.prompt("Synapse admin user token", default=token_default)
    api_base_url = click.prompt(
      "Synapse base URL",
      default=base_url_default)
    conf_dict = {"user": api_user, "token": api_token, "base_url": api_base_url}
    configuration.write(conf_dict)


### the version command starts here ###
@synadm.command(context_settings=cont_set)
@click.pass_context
def version(ctx):
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)

    version = synadm.version()
    if version == None:
        click.echo("Version could not be fetched.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(version)
    else:
        click.echo("Synapse version: {}".format(version['server_version']))
        click.echo("Python version: {}".format(version['python_version']))




#######################################
### user commands group starts here ###
#######################################
@synadm.group(context_settings=cont_set)
@click.pass_context
def user(ctx):
    """list, add, modify, deactivate/erase users,
       reset passwords.
    """


#### user commands start here ###
@user.command(context_settings=cont_set)
@click.option('--from', '-f', 'from_', type=int, default=0, show_default=True,
      help="offset user listing by given number. This option is also used for pagination.")
@click.option('--limit', '-l', type=int, default=100, show_default=True,
      help="limit user listing to given number")
@click.option('--no-guests', '-N', is_flag=True, default=True, show_default=True,
      help="don't show guest users")
@click.option('--deactivated', '-d', is_flag=True, default=False, show_default=True,
      help="also show deactivated/erased users")
#@optgroup.group('Search options', cls=MutuallyExclusiveOptionGroup,
#                help='')
@click.option('--name', '-n', type=str,
      help="""search users by name - the full matrix ID's (@user:server) and
      display names""")
@click.option('--user-id', '-i', type=str,
      help="search users by id - the left part before the colon of the matrix ID's (@user:server)")
@click.pass_context
def list(ctx, from_, limit, no_guests, deactivated, name, user_id):
    log.info(f'user list options: {ctx.params}\n')
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)
    users = synadm.user_list(from_, limit, no_guests, deactivated, name, user_id)
    if users == None:
        click.echo("Users could not be fetched.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(users)
    else:
        click.echo(
              "\nTotal users on homeserver (excluding deactivated): {}\n".format(
              users['total']))
        if int(users['total']) != 0:
            tab_users = get_table(users['users'])
            click.echo(tab_users)
        if 'next_token' in users:
            click.echo(
                "\nThere is more users than shown, use '--from {}' to view them.\n".format(
                users['next_token']))


@user.command(context_settings=cont_set)
@click.argument('user_id', type=str)
      #help='the matrix user ID to deactivate/erase (user:server')
@click.option('--gdpr-erase', '-e', is_flag=True, default=False, show_default=True,
      help="""marks the user as GDPR-erased. This means messages sent by the user
              will still be visible by anyone that was in the room when these messages
              were sent, but hidden from users joining the room afterwards.""")
@click.pass_context
def deactivate(ctx, user_id, gdpr_erase):
    """deactivate or gdpr-erase users. Provide matrix user ID (@user:server) as argument.
    """
    log.info(f'user deactivate options: {ctx.params}\n')
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)
    deactivated = synadm.user_deactivate(user_id, gdpr_erase)
    if deactivated == None:
        click.echo("User could not be deactivated/erased.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(deactivated)
    else:
        if deactivated['id_server_unbind_result'] == 'success':
            click.echo('User successfully deactivated/erased.')
        else:
            click.echo('Synapse returned: {}'.format(deactivated['id_server_unbind_result']))


@user.command(context_settings=cont_set)
@click.argument('user_id', type=str)
@click.option('--no-logout', '-n', is_flag=True, default=False,
      help="don't log user out of all sessions on all devices.")
@click.option('--password', '-p', prompt=True, hide_input=True,
              confirmation_prompt=True, help="new password")
@click.pass_context
def password(ctx, user_id, password, no_logout):
    """change a user's password. To prevent the user from being logged out of all
       sessions use option -n
    """
    m='user password options: user_id: {}, password: secrect, no_logout: {}'.format(
            ctx.params['user_id'], ctx.params['no_logout'])
    log.info(m)
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)
    changed = synadm.user_password(user_id, password, no_logout)
    if changed == None:
        click.echo("Password could not be reset.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(changed)
    else:
        if changed == {}:
            click.echo('Password reset successfully.')
        else:
            click.echo('Synapse returned: {}'.format(changed))


@user.command(context_settings=cont_set)
@click.argument('user_id', type=str)
@click.pass_context
def membership(ctx, user_id):
    '''list all rooms a user is member of. Provide matrix user ID (@user:server) as argument.'''
    log.info(f'user membership options: {ctx.params}\n')
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)
    joined_rooms = synadm.user_membership(user_id)
    if joined_rooms == None:
        click.echo("Membership could not be fetched.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(joined_rooms)
    else:
        click.echo(
              "\nUser is member of {} rooms.\n".format(
              joined_rooms['total']))
        if int(joined_rooms['total']) != 0:
            # joined_rooms is just a list, we don't need get_table() tabulate wrapper
            # (it's for key-value json data aka dicts). Just simply print the list:
            for room in joined_rooms['joined_rooms']:
                click.echo(room)

                
                

#######################################
### room commands group starts here ###
#######################################
@synadm.group(context_settings=cont_set)
def room():
    """list/delete rooms, show/invite/join members, ...
    """


### room commands start here ###
@room.command(context_settings=cont_set)
@click.pass_context
@click.option('--from', '-f', 'from_', type=int, default=0, show_default=True,
      help="""offset room listing by given number. This option is also used
      for pagination.""")
@click.option('--limit', '-l', type=int, default=100, show_default=True,
      help="Maximum amount of rooms to return.")
@click.option('--name', '-n', type=str,
      help="""Filter rooms by their room name. Search term can be contained in
      any part of the room name)""")
@click.option('--order-by', '-o', type=click.Choice(['name', 'canonical_alias',
      'joined_members', 'joined_local_members', 'version', 'creator',
      'encryption', 'federatable', 'public', 'join_rules', 'guest_access',
      'history_visibility', 'state_events']),
      help="The method in which to sort the returned list of rooms.")
@click.option('--reverse', '-r', is_flag=True, default=False,
      help="""Direction of room order. If set it will reverse the sort order of
      --order-by method.""")
def list(ctx, from_, limit, name, order_by, reverse):
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)
    rooms = synadm.room_list(from_, limit, name, order_by, reverse)
    if rooms == None:
        click.echo("Rooms could not be fetched.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(rooms)
    else:
        if int(rooms['total_rooms']) != 0:
            tab_rooms = get_table(rooms['rooms'])
            click.echo(tab_rooms)
        if 'next_batch' in rooms:
            m_n = "\nThere is more rooms than shown, use '--from {}' ".format(
                  rooms['next_batch'])
            m_n+="to go to next page.\n"
            click.echo(m_n)


@room.command(context_settings=cont_set)
@click.argument('room_id', type=str)
@click.pass_context
def details(ctx, room_id):
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)
    room = synadm.room_details(room_id)
    if room == None:
        click.echo("Room details could not be fetched.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(room)
    else:
        if room != {}:
            tab_room = get_table(room, listify=True)
            click.echo(tab_room)

@room.command(context_settings=cont_set)
@click.argument('room_id', type=str)
@click.pass_context
def members(ctx, room_id):
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)
    members = synadm.room_members(room_id)
    if members == None:
        click.echo("Room members could not be fetched.")
        raise SystemExit(1)

    if ctx.obj['raw']:
        pprint(members)
    else:
        click.echo(
              "\nTotal members in room: {}\n".format(
              members['total']))
        if int(members['total']) != 0:
            for member in members['members']:
                click.echo(member)

@room.command(context_settings=cont_set)
@click.pass_context
@click.argument('room_id', type=str)
@click.option('--new-room-user-id', '-u', type=str,
      help='''If set, a new room will be created with this user ID as the
      creator and admin, and all users in the old room will be moved into
      that room. If not set, no new room will be created and the users will
      just be removed from the old room. The user ID must be on the local
      server, but does not necessarily have to belong to a registered
      user.''')
@click.option('--room-name', '-n', type=str,
       help='''A string representing the name of the room that new users will
       be invited to. Defaults to "Content Violation Notification"''')
@click.option('--message', '-m', type=str,
      help='''A string containing the first message that will be sent as
      new_room_user_id in the new room. Ideally this will clearly convey why
      the original room was shut down. Defaults to "Sharing illegal content
      on this server is not permitted and rooms in violation will be
      blocked."''')
@click.option('--block', '-b', is_flag=True, default=False, show_default=True,
      help='''If set, this room will be added to a blocking list,
      preventing future attempts to join the room''')
@click.option('--no-purge', is_flag=True, default=False, show_default=True,
      help='''Prevent removing of all traces of the room from your
      database.''')
def delete(ctx, room_id, new_room_user_id, room_name, message, block, no_purge):
    synadm = Synapse_admin(ctx.obj['config'].user, ctx.obj['config'].token,
          ctx.obj['config'].base_url)

    ctx.invoke(details, room_id=room_id)
    ctx.invoke(members, room_id=room_id)

    sure = click.prompt("\nAre you sure you want to delete this room? (y/N)",
          type=bool, default=False, show_default=False)
    if sure:
        room_del = synadm.room_delete(room_id, new_room_user_id, room_name,
              message, block, no_purge)
        if room_del == None:
            click.echo("Room not deleted.")
            raise SystemExit(1)

        if ctx.obj['raw']:
            pprint(room_del)
        else:
            if room_del != {}:
                tab_room = get_table(room_del, listify=True)
                click.echo(tab_room)
    else:
        click.echo('Abort.')





if __name__ == '__main__':
    synadm(obj={})
