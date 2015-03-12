import logging
from pprint import PrettyPrinter

import click
from twython import Twython
from terminaltables import AsciiTable

def ids_from_search(engine, limit, **search_params):
    """
    Generator to return tweet ids from a twitter search.

    Keeps getting results from twitter till limit is reached or no more tweets
    are returned.

    `engine` should be a Twython instance or something like it that has a method
             `search`.
    `limit` is max number of id to return.  0 for no limit.
    `search_params` are kwargs passed directly to twitter as search parameters.
    """
    response = engine.search(**search_params)

    logging.debug('Params: %s ' % search_params)
    logging.debug('Response: %s' % response.get('search_metadata'))
    logging.debug('Number: %s' % len(response.get('statuses')))

    i = 0
    while response.get('statuses', {}):
        current_min = None
        for status in response.get('statuses'):
            yield status.get('id')

            i = i + 1
            if i == limit:
                return

            if not current_min or status.get('id') < current_min:
                current_min = status.get('id')

        search_params['max_id'] = current_min - 1
        response = engine.search(**search_params)

        logging.debug('Params: %s ' % search_params)
        logging.debug('Response: %s' % response.get('search_metadata'))
        logging.debug('Number: %s' % len(response.get('statuses')))



@click.command()
@click.argument('query')
@click.option('--debug', default=False, is_flag=True, help='Log extra info about searches to stderr.')
@click.option('--bearer_token', help='Twitter oAuth 2 application bearer token.')
@click.option('--consumer_key', help='Twitter oAuth 1.1 consumer app key.')
@click.option('--consumer_secret', help='Twitter oAuth 1.1 consumer app secret.')
@click.option('--access_token', help='Twitter oAuth 1.1 access token.')
@click.option('--access_token_secret', help='Twitter oAuth 1.1 access token secret.')
@click.option('--limit', default=50, help='Limit the number of search results (default 50). 0 for no limit.')
def main(
    query,
    debug,
    bearer_token,
    consumer_key,
    consumer_secret,
    access_token,
    access_token_secret,
    limit,
):
    """
    Run some searches on twitter to see how well the since_id and max_id
    parameters are working.

    The search query to run should be passed as a command-line argument.

    Twitter auth details may be passed as command-line options, or read from
    environment variables (if prefixed with TT, e.g. TT_BEARER_TOKEN)

    Prints out a table showing all the tweet_ids that were returned, and which
    search returned them.
    """

    # Set up basic logging to stderr
    logging.basicConfig(format='%(message)s')
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)


    # Construct a twython instance to run the searches.  Either using
    # application only bearer token or consumer app and user access tokens.
    engine = None
    if bearer_token:
        engine = Twython(access_token=bearer_token, oauth_version=2)
    elif (
        consumer_key
        and consumer_secret
        and access_token
        and access_token_secret
    ):
        engine = Twython(
            app_key=consumer_key,
            app_secret=consumer_secret,
            oauth_token=access_token,
            oauth_token_secret=access_token_secret,
            oauth_version=1,
        )

    if not engine:
        click.echo(
            'Either [bearer_token] or all of [consumer_key, consumer_secret, '
            'access_token_secret, access_token_secret] must be provided to run'
            ' the searches on twitter.'
        )
        return


    initial_params = {
        'q': query,
        'result_type': 'recent',
        'count': 100 if not limit else min(limit, 100)
    }

    # Run a search with no max or since_id.  This gives us bounds to use for our
    # next searches, and provides a base point for comparision.
    initial_ids = list(ids_from_search(engine, limit, **initial_params))

    if not initial_ids:
        click.echo('Sorry folks, no results!')
        return

    max_id = max(initial_ids)
    min_id = min(initial_ids)

    # Run a search using a max_id
    max_only_params = initial_params.copy()
    max_only_params['max_id'] = max_id
    max_only_ids = list(ids_from_search(engine, limit, **max_only_params))

    # Run a search using a max_id and since_id
    max_and_since_params = max_only_params.copy()
    max_and_since_params['since_id'] = min_id - 1
    max_and_since_ids = list(
        ids_from_search(engine, limit, **max_and_since_params)
    )

    # Start constructing the table to show our results.
    pprinter = PrettyPrinter(width=20)
    table_headings = []
    table_headings.append('tweet ids')
    table_headings.append(pprinter.pformat(initial_params))
    table_headings.append(pprinter.pformat(max_only_params))
    table_headings.append(pprinter.pformat(max_and_since_params))

    table_data = [table_headings]

    for twid in sorted(
        set.union(set(initial_ids), set(max_only_ids), set(max_and_since_ids)),
        reverse=True
    ):
        table_data.append(
            [
                str(twid),
                'x' if twid in initial_ids else '',
                'x' if twid in max_only_ids else '',
                'x' if twid in max_and_since_ids else '',
            ]
        )

    # Print the nice table
    click.echo(AsciiTable(table_data).table)


if __name__ == '__main__':
    main(auto_envvar_prefix='TT')
