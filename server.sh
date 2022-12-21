#!/bin/bash

set -e

PID_FILE=server.pid
WATCH_FILE=buildy.py

function start_server {
	test ! -f $PID_FILE
    echo "start server"
	(./buildy.py & echo $! > $PID_FILE)
}

function stop_server {
	test -f $PID_FILE
    echo "stop server"
	kill $(cat $PID_FILE)
	while kill -0 $(cat $PID_FILE) 2> /dev/null; do sleep 1; done;
	rm -f $PID_FILE
}

function restart_server {
	stop_server
	start_server
}

function watch_server {
    echo "watch server"
	start_server
	echo $$ > watch.pid
	while [ -f watch.pid ]; do \
	  watch -gn .1 stat -c %Z $WATCH_FILE ; \
	done
	rm -f watch.pid
	stop_server
}

function stop_watch_server {
    echo "stop watch server"
	kill $(cat watch.pid)
	rm -f watch.pid
	stop_server
}


case $1 in

  start)
    start_server
    ;;

  stop)
    stop_server
    ;;

  restart)
    restart_server
    ;;

  watch)
    watch_server
    ;;

  stop_watch)
    stop_watch_server
    ;;

  *)
    echo -n "don't know what to do! commands: start, stop, restart, watch stop_watch"
    exit 1
    ;;
esac
