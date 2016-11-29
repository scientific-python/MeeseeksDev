import os
import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web

class MainHandler(tornado.web.RequestHandler):

    def get(self):
        self.finish('No')

def main():
    application = tornado.web.Application([
        (r"/", MainHandler),
    ])

    port = int(os.environ.get('PORT', 5000))
    tornado.httpserver.HTTPServer(application).listen(port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
