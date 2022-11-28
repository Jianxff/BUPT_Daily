from base import *
from crawl import crawler

if __name__ == '__main__':
    cl = crawler(in_school = False)
    
    # login retry times 5
    for i in range(0,5):
        if cl.login() == 200:
            break
        cl = crawler(in_school = False)   # update crawler
        logging.warn('log in failed. retrying in 5 sec...') # retry
        time.sleep(5)
    
    cl.catch()  # catch news 

   