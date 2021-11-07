import sqlite3
import cgi
import json
import boto3

def get_pics(environ, start_response):
    #default encoding for json is utf-8
    start_response('200 OK', [('Content-type', 'application/json')])
    #get info from db
    db = sqlite3.connect('../db/pics.db')
    c = db.cursor()
    c.execute('select * from pics')
    resp = c.fetchall()
    data = {"results": []}
    for row in resp:
        data["results"].append({'uri': row[0], 'caption': row[1], 'name': row[2]})
    db.close()
    res = json.dumps(data)
    yield res.encode('utf-8')

def get_pic(environ, start_response):
    start_response('200 OK', [('Content-type', 'application/json')])
    params = environ['params']
    name=params.get('name')
    db = sqlite3.connect('../db/pics.db')
    c = db.cursor()
    c.execute('select * from pics where name=(?)', (name,))
    resp = c.fetchall()
    data = {"results": []}
    for row in resp:
        data["results"].append({'uri': row[0], 'caption': row[1], 'name': row[2]})
        db.close()
        res = json.dumps(data)
        yield res.encode('utf-8')

def upload_pic(environ, start_response):
    response_data = environ['params']
    client = boto3.client('s3')
    bucket = 'squarespics'
    img = response_data.get('file')
    name = response_data.get('name')
    caption = response_data.get('caption')

    if not name:
        start_response('400 Bad Request', [('Content-type', 'application/json')])
        return [b'Name required']

    #connect to db
    db = sqlite3.connect('../db/pics.db')
    res = db.execute('select * from pics where name = ?', (name,))

    if res.fetchone():
        db.close()
        start_response('400 Bad Request', [('Content-type', 'application/json')])
        return [b'Choose new name']


    #first check name and whether is unique
    #if not unique update
    if img:
        try:
            response = client.put_object(Body=img,
                                         Bucket=bucket,
                                         Key=name,
                                         ContentType='image/jpeg')
        except:
            return([b'500'])
    else:
        print(response_data.keys())
        return [b'400 Bad Request']

    #if no exception image successfully updated
    db.execute('insert into pics(uri, name, caption) values (?,?,?)',
               ('https://squarespics.s3.amazonaws.com/' + name, name, caption))
    db.commit()
    db.close()

    start_response('200 OK', [('Content-type', 'application/json')])

    return [b'Success']

def notfound_404(environ, start_response):
    start_response('404 Not Found', [ ('Content-type', 'text/plain') ])
    return [b'Not Found']


class PathDispatcher:
    def __init__(self):
        self.pathmap = {}

    def __call__(self, environ, start_response):
        path = environ['PATH_INFO']
        params = cgi.FieldStorage(environ['wsgi.input'],
                                  environ=environ)
        method = environ['REQUEST_METHOD'].lower()
        environ['params'] = { key: params.getvalue(key) for key in params }
        handler = self.pathmap.get((method,path), notfound_404)
        return handler(environ, start_response)

    def register(self, method, path, function):
        self.pathmap[method.lower(), path] = function
        return function


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    dispatcher = PathDispatcher()
    dispatcher.register('GET', '/pics', get_pics)
    dispatcher.register('POST', '/post', upload_pic)
    dispatcher.register('GET', '/pic', get_pic)
    httpd = make_server('', 8080, dispatcher)
    print('Serving on port 8080...')
    httpd.serve_forever()

