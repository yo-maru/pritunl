import pritunl

import optparse
import sys
import os
import time
import json

USAGE = """\
Usage: pritunl [command] [options]
Command Help: pritunl [command] --help

Commands:
  start                 Start server
  version               Print the version and exit
  setup-key             Print the setup key and exit
  default-password      Print the default administrator password
  reset-password        Reset administrator password
  reset-version         Reset database version to server version
  reset-ssl-cert        Reset the server ssl certificate
  renew-ssl-cert        Renew the Lets Encrypt server ssl certificate
  reconfigure           Reconfigure database connection
  clear-message-cache   Clear the cache of the internal message system
  override-device-key   Allow device registration without key for 8 hours
  require-device-key    Remove device registration key override
  get-mongodb           Get the current mongodb uri
  set-mongodb           Set the mongodb uri
  get-host-id           Get the current host id
  set-host-id           Set the host id
  logs                  View server logs
  clear-auth-limit      Reset failed authentication attempt limiter
  clear-logs            Clear server logs"""

def main(default_conf=None):
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
    else:
        cmd = 'start'

    parser = optparse.OptionParser(usage=USAGE)

    if cmd == 'start':
        parser.add_option('-d', '--daemon', action='store_true',
            help='Daemonize process')
        parser.add_option('-p', '--pidfile', type='string',
            help='Path to create pid file')
        parser.add_option('-c', '--conf', type='string',
            help='Path to configuration file')
        parser.add_option('-q', '--quiet', action='store_true',
            help='Suppress logging output')
    elif cmd == 'logs':
        parser.add_option('--archive', action='store_true',
            help='Archive log file')
        parser.add_option('--tail', action='store_true',
            help='Tail log file')
        parser.add_option('--limit', type='int',
            help='Limit log lines')
        parser.add_option('--natural', action='store_true',
            help='Natural log sort')
        parser.add_option('--unformatted', action='store_true',
            help='Disable terminal color formatting')
    elif cmd == 'set':
        parser.disable_interspersed_args()

    (options, args) = parser.parse_args()

    if hasattr(options, 'conf') and options.conf:
        conf_path = options.conf
    else:
        conf_path = default_conf
    pritunl.set_conf_path(conf_path)

    if cmd == 'version':
        print('%s v%s' % (pritunl.__title__, pritunl.__version__))
        sys.exit(0)
    elif cmd == 'setup-key':
        from pritunl import setup
        from pritunl import settings

        setup.setup_loc()
        print(settings.local.setup_key)

        sys.exit(0)
    elif cmd == 'reset-version':
        from pritunl.constants import MIN_DATABASE_VER
        from pritunl import setup
        from pritunl import utils

        setup.setup_db()
        utils.set_db_ver(pritunl.__version__, MIN_DATABASE_VER)

        time.sleep(.2)
        print('Database version reset to %s' % pritunl.__version__)

        sys.exit(0)
    elif cmd == 'reset-password':
        from pritunl import setup
        from pritunl import auth

        setup.setup_db()
        username, password = auth.reset_password()

        print('Administrator password successfully reset:\n' + \
            '  username: "%s"\n  password: "%s"' % (username, password))

        sys.exit(0)
    elif cmd == 'default-password':
        from pritunl import setup
        from pritunl import auth

        setup.setup_db()
        username, password = auth.get_default_password()

        if not password:
            print('No default password available, use reset-password')
        else:
            print('Administrator default password:\n' + \
                '  username: "%s"\n  password: "%s"' % (username, password))

        sys.exit(0)
    elif cmd == 'reconfigure':
        from pritunl import setup
        from pritunl import settings
        setup.setup_loc()

        settings.conf.mongodb_uri = None
        settings.conf.commit()

        time.sleep(.2)
        print('Database configuration successfully reset')

        sys.exit(0)
    elif cmd == 'get':
        from pritunl import setup
        from pritunl import settings
        setup.setup_db_host()

        if len(args) != 2:
            raise ValueError('Invalid arguments')

        split = args[1].split('.')
        key_str = None
        group_str = split[0]
        if len(split) > 1:
            key_str = split[1]

        if group_str == 'host':
            group = settings.local.host
        else:
            group = getattr(settings, group_str)

        if key_str:
            val = getattr(group, key_str)
            print('%s.%s = %s' % (group_str, key_str,
                json.dumps(val, default=lambda x: str(x))))

        else:
            for field in group.fields:
                val = getattr(group, field)
                print('%s.%s = %s' % (group_str, field,
                    json.dumps(val, default=lambda x: str(x))))

        sys.exit(0)
    elif cmd == 'set':
        from pritunl.constants import HOSTS_UPDATED
        from pritunl import setup
        from pritunl import settings
        from pritunl import event
        from pritunl import messenger
        setup.setup_db_host()

        if len(args) != 3:
            raise ValueError('Invalid arguments')

        group_str, key_str = args[1].split('.')

        if group_str == 'host':
            group = settings.local.host
        else:
            group = getattr(settings, group_str)

        val_str = args[2]
        try:
            val = json.loads(val_str)
        except ValueError:
            val = json.loads(json.JSONEncoder().encode(val_str))

        setattr(group, key_str, val)

        if group_str == 'host':
            settings.local.host.commit()

            event.Event(type=HOSTS_UPDATED)
            messenger.publish('hosts', 'updated')
        else:
            settings.commit()

        time.sleep(.2)

        print('%s.%s = %s' % (group_str, key_str,
            json.dumps(getattr(group, key_str), default=lambda x: str(x))))
        print('Successfully updated configuration. This change is ' \
            'stored in the database and has been applied to all hosts ' \
            'in the cluster.')

        sys.exit(0)
    elif cmd == 'unset':
        from pritunl import setup
        from pritunl import settings
        setup.setup_db()

        if len(args) != 2:
            raise ValueError('Invalid arguments')

        group_str, key_str = args[1].split('.')

        group = getattr(settings, group_str)

        group.unset(key_str)

        settings.commit()

        time.sleep(.2)

        print('%s.%s = %s' % (group_str, key_str,
            json.dumps(getattr(group, key_str), default=lambda x: str(x))))
        print('Successfully updated configuration. This change is ' \
            'stored in the database and has been applied to all hosts ' \
            'in the cluster.')

        sys.exit(0)
    elif cmd == 'override-device-key':
        from pritunl import setup
        from pritunl import settings
        setup.setup_db_host()

        settings.user.device_key_override = int(time.time())
        settings.commit()

        time.sleep(.2)

        print('Device registration key override active for 8 hours. ' +
            'Use command require-device-key to reactivate.')

        sys.exit(0)
    elif cmd == 'require-device-key':
        from pritunl import setup
        from pritunl import settings
        setup.setup_db_host()

        settings.user.device_key_override = None
        settings.commit()

        time.sleep(.2)

        print('Device registration key override deactivated.')

        sys.exit(0)
    elif cmd == 'get-mongodb':
        from pritunl import setup
        from pritunl import settings
        setup.setup_loc()

        print(settings.conf.mongodb_uri)

        sys.exit(0)
    elif cmd == 'set-mongodb':
        from pritunl import setup
        from pritunl import settings
        setup.setup_loc()

        if len(args) > 1:
            mongodb_uri = args[1]
        else:
            mongodb_uri = None

        settings.conf.mongodb_uri = mongodb_uri
        settings.conf.commit()

        time.sleep(.2)
        print('Database configuration successfully set')

        sys.exit(0)
    elif cmd == 'get-host-id':
        from pritunl import setup
        from pritunl import settings
        setup.setup_loc()

        print(settings.local.host_id)

        sys.exit(0)
    elif cmd == 'set-host-id':
        from pritunl import setup
        from pritunl import settings
        setup.setup_loc()

        if len(args) > 1:
            host_id = args[1]
        else:
            host_id = None

        with open(settings.conf.uuid_path, 'w') as uuid_file:
            uuid_file.write(host_id.strip())

        time.sleep(.2)
        print('Host ID successfully set')

        sys.exit(0)
    elif cmd == 'reset-ssl-cert':
        from pritunl import setup
        from pritunl import settings
        setup.setup_db()

        settings.app.server_cert = None
        settings.app.server_key = None
        settings.app.acme_timestamp = None
        settings.app.acme_key = None
        settings.app.acme_domain = None
        settings.commit()

        time.sleep(.2)
        print('Server ssl certificate successfully reset')

        sys.exit(0)
    elif cmd == 'renew-ssl-cert':
        from pritunl import setup
        from pritunl import settings
        from pritunl import acme
        setup.setup_db()

        if not settings.app.acme_domain:
            print('Server does not have Lets Encrypt domain configured')
            sys.exit(0)

        acme.update_acme_cert(True)

        time.sleep(.2)
        print('Server ssl certificate successfully renewed')

        sys.exit(0)
    elif cmd == 'clear-message-cache':
        from pritunl import setup
        from pritunl import logger
        from pritunl import mongo

        setup.setup_db()

        print('Clearing message cache...')

        mongo.get_collection('messages').drop()
        mongo.secondary_database.create_collection(
            prefix + 'messages', capped=True,
            size=5000192, max=1000)

        print('Message cache cleared')

        sys.exit(0)
    elif cmd == 'destroy-secondary':
        from pritunl import setup
        from pritunl import logger
        from pritunl import mongo

        setup.setup_db()

        print('Destroying secondary database...')

        mongo.get_collection('clients').drop()
        mongo.get_collection('clients_pool').drop()
        mongo.get_collection('transaction').drop()
        mongo.get_collection('queue').drop()
        mongo.get_collection('tasks').drop()

        mongo.get_collection('messages').drop()
        mongo.get_collection('users_key_link').drop()
        mongo.get_collection('auth_sessions').drop()
        mongo.get_collection('auth_csrf_tokens').drop()
        mongo.get_collection('auth_limiter').drop()
        mongo.get_collection('otp').drop()
        mongo.get_collection('otp_cache').drop()
        mongo.get_collection('sso_tokens').drop()
        mongo.get_collection('sso_push_cache').drop()
        mongo.get_collection('sso_client_cache').drop()
        mongo.get_collection('sso_passcode_cache').drop()

        setup.upsert_indexes()

        server_coll = mongo.get_collection('servers')
        server_coll.update_many({}, {
            '$set': {
                'status': 'offline',
                'instances': [],
                'instances_count': 0,
            },
            '$unset': {
                'network_lock': '',
                'network_lock_ttl': '',
            },
        })

        print('Secondary database destroyed')

        sys.exit(0)
    elif cmd == 'repair-database':
        from pritunl import setup
        from pritunl import logger
        from pritunl import mongo

        setup.setup_db()

        print('Repairing database...')

        mongo.get_collection('clients').drop()
        mongo.get_collection('clients_pool').drop()
        mongo.get_collection('transaction').drop()
        mongo.get_collection('queue').drop()
        mongo.get_collection('tasks').drop()

        mongo.get_collection('messages').drop()
        mongo.get_collection('users_key_link').drop()
        mongo.get_collection('auth_sessions').drop()
        mongo.get_collection('auth_csrf_tokens').drop()
        mongo.get_collection('auth_limiter').drop()
        mongo.get_collection('otp').drop()
        mongo.get_collection('otp_cache').drop()
        mongo.get_collection('sso_tokens').drop()
        mongo.get_collection('sso_push_cache').drop()
        mongo.get_collection('sso_client_cache').drop()
        mongo.get_collection('sso_passcode_cache').drop()
        mongo.get_collection('acme_challenges').drop()

        mongo.get_collection('logs').drop()
        mongo.get_collection('log_entries').drop()
        mongo.get_collection('servers_ip_pool').drop()

        setup.upsert_indexes()

        server_coll = mongo.get_collection('servers')
        server_coll.update_many({}, {
            '$set': {
                'status': 'offline',
                'instances': [],
                'instances_count': 0,
            },
            '$unset': {
                'network_lock': '',
                'network_lock_ttl': '',
            },
        })

        from pritunl import server

        for svr in server.iter_servers():
            try:
                svr.ip_pool.sync_ip_pool()
            except:
                logger.exception('Failed to sync server IP pool', 'tasks',
                    server_id=svr.id,
                )

        server_coll.update_many({}, {
            '$set': {
                'status': 'offline',
                'instances': [],
                'instances_count': 0,
            },
            '$unset': {
                'network_lock': '',
                'network_lock_ttl': '',
            },
        })

        print('Database repair complete')

        sys.exit(0)
    elif cmd == 'logs':
        from pritunl import setup
        from pritunl import logger
        setup.setup_db()

        log_view = logger.LogView()

        if options.archive:
            if len(args) > 1:
                archive_path = args[1]
            else:
                archive_path = './'
            print('Log archived to: ' + log_view.archive_log(archive_path,
                options.natural, options.limit))
        elif options.tail:
            for msg in log_view.tail_log_lines():
                print(msg)
        else:
            print(log_view.get_log_lines(
                natural=options.natural,
                limit=options.limit,
                formatted=not options.unformatted,
            ))

        sys.exit(0)
    elif cmd == 'clear-auth-limit':
        from pritunl import setup
        from pritunl import logger
        from pritunl import mongo
        from pritunl import settings

        setup.setup_db()

        mongo.get_collection('auth_limiter').delete_many({})

        print('Auth limiter cleared')

        sys.exit(0)
    elif cmd == 'clear-logs':
        from pritunl import setup
        from pritunl import logger
        from pritunl import mongo
        from pritunl import settings

        setup.setup_db()

        mongo.get_collection('logs').drop()
        mongo.get_collection('log_entries').drop()

        prefix = settings.conf.mongodb_collection_prefix or ''

        log_limit = settings.app.log_limit
        mongo.database.create_collection(prefix + 'logs', capped=True,
            size=log_limit * 1024, max=log_limit)

        log_entry_limit = settings.app.log_entry_limit
        mongo.database.create_collection(prefix + 'log_entries', capped=True,
            size=log_entry_limit * 512, max=log_entry_limit)

        print('Log entries cleared')

        sys.exit(0)
    elif cmd != 'start':
        raise ValueError('Invalid command')

    from pritunl import settings

    if options.quiet:
        settings.local.quiet = True

    if options.daemon:
        pid = os.fork()
        if pid > 0:
            if options.pidfile:
                with open(options.pidfile, 'w') as pid_file:
                    pid_file.write('%s' % pid)
            sys.exit(0)
    elif not options.quiet:
        print('##############################################################')
        print('#                                                            #')
        print('#                      /$$   /$$                         /$$ #')
        print('#                     |__/  | $$                        | $$ #')
        print('#   /$$$$$$   /$$$$$$  /$$ /$$$$$$   /$$   /$$ /$$$$$$$ | $$ #')
        print('#  /$$__  $$ /$$__  $$| $$|_  $$_/  | $$  | $$| $$__  $$| $$ #')
        print('# | $$  \ $$| $$  \__/| $$  | $$    | $$  | $$| $$  \ $$| $$ #')
        print('# | $$  | $$| $$      | $$  | $$ /$$| $$  | $$| $$  | $$| $$ #')
        print('# | $$$$$$$/| $$      | $$  |  $$$$/|  $$$$$$/| $$  | $$| $$ #')
        print('# | $$____/ |__/      |__/   \____/  \______/ |__/  |__/|__/ #')
        print('# | $$                                                       #')
        print('# | $$                                                       #')
        print('# |__/                                                       #')
        print('#                                                            #')
        print('##############################################################')

    pritunl.init_server()

if __name__ == '__main__':
    main()
