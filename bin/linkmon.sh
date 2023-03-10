logfile=$HOME/linkmon.txt
timeLimit=3000                  # default: 50min before shutdown.
loopDelay=3

usage() {
    error=$1

    if test -n "$error"; then
	echo "error: $error"
	echo
    fi 1>&2

    echo "usage: $0 [-n] [-t timeLimit] [-d loopDelay]" 1>&2
    exit 1;
}

norun=false
while getopts "nt:d:" opt; do
    case "$opt" in
	n)
	    norun=true
	    ;;
	t)
	    timeLimit=${OPTARG}
	    ;;
	d)
	    loopDelay=${OPTARG}
	    ;;
	*)
	    usage
	    ;;
    esac
done
shift $((OPTIND-1))

logit () {
    msg="$(date +'%Y-%m-%dT%H:%M:%S')    $@"
    echo $msg >> $logfile
    echo $msg >&2
}

getLink () {
    return $(ip link show eth0 | grep -q LOWER_UP)
}
getLinkName () {
    if getLink; then
	echo up
    else
	echo down
    fi
}
updateLinkState () {
    oldState=$1
    newState=$(getLinkName)
    if test "$newState" != "$oldState"; then
	logit "$oldState $newState"
    fi

    echo $newState
}

getTimer () {
    echo "$(date +%s)"
}
checkTimer () {
    now=$(getTimer)
    if ((stopTime == 0)); then
	stopTime=$(($now + $timeLimit))
    fi
    logit "$stopTime $now $(($stopTime - $now))"
    return $(($now < $stopTime))
}
stopTimer () {
    stopTime=0
}

echo "running norun=$norun timeLimit=$timeLimit loopDelay=$loopDelay"
stopTimer
state=unknown
while true; do
    state=$(updateLinkState $state)
    if test $state = "up"; then
	stopTimer
    else
	if checkTimer; then
	    if $norun; then
		logit "down notShutdown"
		echo sudo /sbin/shutdown -h now
	    else
		logit "down shutdown"
		sudo /sbin/shutdown -h now
	    fi
	    exit 1
	fi
    fi

    sleep $loopDelay
done
