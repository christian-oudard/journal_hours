#! /usr/bin/env python3

import sys

import time
from datetime import date, datetime, timedelta

date_format = '%Y-%m-%d'
time_format = '%H:%M'


class IntervalError(ValueError):
    pass


def main():
    with open(sys.argv[1]) as f:
        lines = [ l.strip() for l in f.readlines() ]

    # Parse hourly rate.
    if len(sys.argv) == 5:
        hourly_rate = int(sys.argv[4])
    else:
        hourly_rate = None

    # Parse start and end dates if they are given. Inclusive date range.
    if len(sys.argv) >= 4:
        start_date = parse_date(sys.argv[2])
        end_date = parse_date(sys.argv[3])
        assert start_date is not None
        assert end_date is not None
    elif len(sys.argv) == 3:  # Single date for start and end.
        start_date = parse_date(sys.argv[2])
        end_date = parse_date(sys.argv[2])
        assert start_date is not None
        assert end_date is not None
    else:
        start_date = None
        end_date = None

    intervals_by_date = process(lines)

    all_intervals = []
    for (d, intervals) in intervals_by_date:
        if len(intervals) == 0:
            continue
        if start_date is not None and d < start_date:
            continue
        if end_date is not None and d >= end_date + timedelta(days=1):
            continue
        all_intervals.extend(intervals)
        elapsed = interval_sum(intervals)
        if hourly_rate is None:
            print('{}: {}'.format(
                d.strftime(date_format),
                format_timedelta(elapsed),
            ))
        else:
            hours = elapsed.total_seconds() / (60 * 60)
            amount = hours * hourly_rate
            print('{}: {} {:>8}'.format(
                d.strftime(date_format),
                format_timedelta(elapsed),
                '${:.2f}'.format(amount),
            ))

        # for (start, end) in intervals:
        #     print('  {} - {}'.format(start.strftime(time_format), end.strftime(time_format)))

    total_elapsed = interval_sum(all_intervals)

    if start_date is None:
        print('Total time worked:')
    else:
        print('Total time worked from {} to {}:'.format(
            start_date.strftime(date_format),
            end_date.strftime(date_format),
        ))

    total_hours = total_elapsed.total_seconds() / (60 * 60)
    print('  {:.2f} hours ({})'.format(total_hours, format_timedelta(total_elapsed)))

    if hourly_rate is not None:
        print('Hourly rate: ${}'.format(hourly_rate))
        print('Total due: ${:.2f}'.format(total_hours * hourly_rate))


def process(lines):
    current_date = None
    current_interval = []
    intervals_by_date = []  # [(current_date, [(start, end)])]

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
        action, t = time_result
        if action == 'start':
            if len(current_interval) == 0:
                current_interval.append(t)
            else:
                raise IntervalError('On line {}, found unexpected interval start.'.format(line_number))
        elif action == 'end':
            if len(current_interval) == 1:
                current_interval.append(t)
                if not (current_interval[0] < current_interval[1]):
                    raise IntervalError('On line {}, found a backward interval.'.format(line_number))
                intervals_by_date[-1][1].append(current_interval)
                current_interval = []
            else:
                raise IntervalError('On line {}, found unexpected interval end.'.format(line_number))

    # If the ending interval is open and on the current day, simulate closing the interval right now.
    if len(current_interval) == 1:
        if current_date == date.today():
            now = datetime.now()
            if current_interval[0] < now:
                current_interval.append(now)
                intervals_by_date[-1][1].append(current_interval)

    return intervals_by_date


def parse_time(line, current_date):
    if ' ' not in line:
        return None

    action, time_string = line.split(' ', 1)
    if action not in ['start', 'end']:
        return None

    try:
        t = time.strptime(time_string, time_format)
    except ValueError:
        return None

    if current_date is None:
        raise IntervalError('Found interval start before any date markers.')

    t = assemble_datetime(current_date, t)
    return (action, t)


def interval_sum(intervals):
    total = timedelta()
    for (start, end) in intervals:
        total += end - start
    return total


def format_timedelta(td):
    hours, rem = divmod(td.total_seconds(), (60 * 60))
    minutes, seconds_ = divmod(rem, 60)
    return '{}h{:02d}m'.format(round(hours), round(minutes))


def parse_date(s):
    try:
        return force_date(datetime.strptime(s, date_format))
    except ValueError:
        return None


def force_date(d):
    """Turn a date or a datetime into a date."""
    return date(d.year, d.month, d.day)


def assemble_datetime(d, t):
    """Make a datetime out of a date and a time. Ignores seconds and microseconds."""
    return datetime(d.year, d.month, d.day, t.tm_hour, minute=t.tm_min)


def flatten(list_of_lists):
    for sublist in list_of_lists:
        for item in sublist:
            yield item


if __name__ == '__main__':
    main()
