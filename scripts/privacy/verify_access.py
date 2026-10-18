"""Fail closed before uploading reports to a pre-protected Cloudflare Pages hostname."""
import argparse
import os
import urllib.error
import urllib.parse
import urllib.request


def check(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query:
        raise ValueError('An HTTPS site URL without credentials or query is required')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    # Verify HTML AND data paths cannot be read anonymously, including missing paths.
    for path in ('/', '/futbol/', '/basketbol/', '/futbol/data/MatchInfo-2000-01-01.json'):
        try:
            response = opener.open(parsed._replace(path=path).geturl(), timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        location = response.headers.get('Location', '')
        redirect = urllib.parse.urlparse(location)
        access_login = (response.code == 302 and redirect.scheme == 'https'
                        and (redirect.hostname or '').endswith('.cloudflareaccess.com')
                        and redirect.path.startswith('/cdn-cgi/access/login'))
        # 403 alone is not proof of Access; require a recognizable Access login redirect.
        if not access_login:
            raise ValueError('Cloudflare Access gate was not verified for every path')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()
    check(args.url)
    print('Anonymous requests reach Cloudflare Access login; verify owner allowlist separately.')
