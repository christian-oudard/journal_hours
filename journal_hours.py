#! /usr/bin/env python3

import sys

from time import strptime
from datetime import datetime, timedelta

date_format = '%Y-%m-%d'
time_format = '%H:%M'


class IntervalError(ValueError):
    pass


def process(lines):
    current_date = None
    current_interval = []
    intervals_by_date = []

    for (line_number, line) in enumerate(lines):
        line = line.strip()

        # Try to find a date.
        d = parse_date(line)
        if d is not None:
            current_date = d
            intervals_by_date.append((current_date, []))

        # Try to find a start or finish time.
        time_result = parse_time(line, current_date)
        if time_result is None:
            continue

        # Ensure that each timestamp is part of a pair.
        is_start, t = time_result
        if is_start:
            if len(current_interval) == 0:
                current_interval.append(t)
            else:
                raise IntervalError('On line {}, found unexpected interval start.'.format(line_number))
        else:  # end
            if len(current_interval) == 1:
                current_interval.append(t)
                assert current_interval[0] < current_interval[1]
                intervals_by_date[-1][1].append(current_interval)
                current_interval = []
            else:
                raise IntervalError('On line {}, found unexpected interval end.'.format(line_number))

    return intervals_by_date


def parse_date(line):
    try:
        return datetime.strptime(line, date_format)
    except ValueError:
        return None


def parse_time(line, current_date):
    if ' ' not in line:
        return None

    action, time_string = line.split(' ', 1)
    if action == 'start':
        is_start = True
    elif action == 'end':
        is_start = False
    else:
        return None

    try:
        t = strptime(time_string, time_format)
    except ValueError:
        return None

    if current_date is None:
        raise IntervalError('Found interval start before any date markers.')

    t = current_date.replace(hour=t.tm_hour, minute=t.tm_min)
    return (is_start, t)


def interval_sum(intervals):
    total = timedelta()
    for (start, end) in intervals:
        total += end - start
    return total


def format_timedelta(td):
    hours, rem = divmod(td.seconds, (60 * 60))
    minutes, seconds = divmod(rem, 60)
    return '{}h{:02d}m'.format(hours, minutes)


def flatten(list_of_lists):
    for sublist in list_of_lists:
        for item in sublist:
            yield item


if __name__ == '__main__':
    with open(sys.argv[1]) as f:
        lines = [ l.strip() for l in f.readlines() ]

    intervals_by_date = process(lines)
    total_seconds = 0
    for (d, intervals) in intervals_by_date:
        if len(intervals) == 0:
            continue
        elapsed = interval_sum(intervals)
        print('{}: {}'.format(d.strftime(date_format), format_timedelta(elapsed)))
        for (start, end) in intervals:
            print('  {} - {}'.format(start.strftime(time_format), end.strftime(time_format)))
        print()

    all_intervals = flatten( ivls for (d_, ivls) in intervals_by_date )
    total_elapsed = interval_sum(all_intervals)
    total_seconds = total_elapsed.days * 60 + total_elapsed.seconds

    print('Total: {} ({:.2f} hours)'.format(
        format_timedelta(total_elapsed),
        total_seconds / (60 * 60),
    ))
