#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import multiprocessing, sys

class Job(object):
    """
    Base class of the jOB
    """
        
    def map(self, pos, item):
        return (pos, item)
    
    def reduce_start(self):
        pass
    
    def reduce(self, key, r):
        pass
        
    def reduce_stop(self):
        pass
        
class WC(Job):
    "Sample Word count parallel implementation"
    lc = 0
    wc = 0 
    bc = 0
    def __init__(self, f):
        self.file = f
    
    def reduce_start(self):
        self.lc = 0
        self.wc = 0
        self.bc = 0 
        
    def enumerate(self):
        return enumerate(open(self.file))
        
    def map(self, pos, item):
        return (pos, (1, len(item.split()), len(item)))
        
    def reduce(self, pos, r):
        (lc, wc, bc) = r
        self.lc = self.lc + lc
        self.wc = self.wc + wc
        self.bc = self.bc + bc
                
    def reduce_stop(self):
        return (self.lc, self.wc, self.bc)

class Runner(object):
    """
    simplemapreduce.Runner wraps up an single-server multi-core of MapReduce
    
    job.enumerate() is called and should returns an enumeration of elements
    
    job.map(i, elt) is called on a separate subprocess for each element. 
        i is the position of the element in the original enumeraiton
        job.map should return a tuple (key, value), where key is an integer.
        key can be None is the order of values is meaningless
    
    job.onReduceStart() is called in the parent process at the begin of reduce processing
    
    job.reduce(key, value) is called on each element in the parent process, in the order of keys
    
    job.onReduceStop() is called in the parent process at the end of reduce processing        
    """ 
    STOP_MSG = "##STOP_MSG##"
    
    def __init__(self, numprocs = None, debug=False):
        self.numprocs = numprocs
        if not self.numprocs:
            self.numprocs = multiprocessing.cpu_count()

        self.inq = multiprocessing.Queue()
        self.outq = multiprocessing.Queue()
        self.debug = debug
        
    def run(self, job):
        self.job = job

        # Process that reads the input file
        self.pin = multiprocessing.Process(target=self.enumerate_and_process_input, args=())
        
        # Line Processes. 
        self.ps = [ multiprocessing.Process(target=self.call_map, args=())
                        for i in range(self.numprocs)]

        if self.debug:
            print "Starting the job with %u processoes" % self.numprocs

        # Start the processes
        self.pin.start()
        for p in self.ps:
            p.start()
            
        ret = self.call_reduce()

        # Join all processors. 
        self.pin.join()
        i = 0
        for p in self.ps:
            p.join()
            if self.debug:
                print >> sys.stderr, "Done", i
            i += 1
        return ret

    def enumerate_and_process_input(self):
        """"
        The data is then sent over inqueue for the workers to do their
        thing.  At the end the input thread sends a 'STOP' message for each
        worker.
        """
        for i, line in self.job.enumerate(): 
            self.inq.put( (i, line))
        for work in range(self.numprocs):
            self.inq.put(self.STOP_MSG)
        if self.debug: 
            print >> sys.stderr, "Input: STOP sent "

    def call_map(self):
        """
        Read lines from input, call process_line for each, and performs output. 
        """
        for i, item in iter(self.inq.get, self.STOP_MSG):
            self.outq.put( self.job.map(i, item) )
        self.outq.put(self.STOP_MSG)
        if self.debug:
            print >> sys.stderr, "Output : STOP sent"
    
    def call_reduce(self):
        """
        Call call_output sequentially, respecting ordering of the initial file. 
        """
        cur = 0
        buffer = {}
        
        self.job.reduce_start()

        for mappers in range(self.numprocs):
            for msg in iter(self.outq.get, self.STOP_MSG):
                (i, val)  = msg 
                # verify rows are in order, if not save in buffer
                if i != cur:
                    buffer[i] = val
                else:
                    self.job.reduce(i, val)
                    cur += 1 
                    while cur in buffer:
                        self.job.reduce(cur, buffer[cur])
                        del buffer[cur]
                        cur += 1
            if self.debug:
                print >> sys.stderr, "Mapper done %u" % mappers
        return self.job.reduce_stop()
        
if __name__ == "__main__":
    runner = Runner()
    for argv in sys.argv[1:]:
        (lc, wc, bc) = runner.run(WC(argv))
        print "\t%u\t%u\t%u\t%s" % (lc, wc, bc, argv)
