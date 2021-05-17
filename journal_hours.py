#! /usr/bin/env python3

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta

date_format = '%Y-%m-%d'
time_format = '%H:%M'
display_time_format = '%I:%M %p'


class IntervalError(ValueError):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', dest='verbose', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--rate', type=int)
    parser.add_argument('journal_file')
    parser.add_argument('start', nargs='?')
    parser.add_argument('end', nargs='?')
    args = parser.parse_args()

    # Parse start and end dates if they are given. Inclusive date range.
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if end_date is None:
        end_date = date.today()

    # Process journal file.
    with open(args.journal_file) as f:
        lines = [ l.strip() for l in f.readlines() ]

    intervals_by_date = process(lines)
    intervals_by_date = [
        (d, intervals)
        for (d, intervals) in intervals_by_date
        if (
            len(intervals) > 0
            and (start_date is None or d >= start_date)
            and (end_date is None or d <= end_date)
        )
    ]

    if args.json:
        json_data = {}
        for (d, intervals) in intervals_by_date:
            json_data[force_timestamp(d)] = [
                (force_timestamp(start), force_timestamp(end))
                for (start, end) in intervals
            ]
        print(json.dumps(json_data))
        return

    all_intervals = []
    for (d, intervals) in intervals_by_date:
        all_intervals.extend(intervals)
        elapsed = interval_sum(intervals)

        out_line = '{}: {}'.format(
            d.strftime(date_format),
            format_timedelta(elapsed),
        )
        if args.rate is not None:
            hours = elapsed.total_seconds() / (60 * 60)
            amount = hours * args.rate
            out_line += ' {:>8}'.format('${:.2f}'.format(amount))
        print(out_line)

        if args.verbose:
            for (start, end) in intervals:
                print('  {} - {}'.format(start.strftime(display_time_format), end.strftime(display_time_format)))

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

    if args.rate is not None:
        print('Hourly rate: ${}'.format(args.rate))
        print('Total due: ${:.2f}'.format(total_hours * args.rate))


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
            if len(intervals_by_date) > 0 and current_date <= intervals_by_date[-1][0]:
                raise IntervalError('On line {}, the date {} was out of order.'.format(line_number, d.strftime(date_format)))
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
                intervals_by_date[-1][1].append(tuple(current_interval))
                current_interval = []
            else:
                raise IntervalError('On line {}, found unexpected interval end.'.format(line_number))

    # If the ending interval is open and on the current day, simulate closing the interval right now.
    if len(current_interval) == 1:
        if current_date == date.today():
            now = datetime.now()
            if current_interval[0] < now:
                current_interval.append(now)
                intervals_by_date[-1][1].append(tuple(current_interval))

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
    except (TypeError, ValueError):
        return None


def force_date(d):
    """Turn a date or a datetime into a date."""
    return date(d.year, d.month, d.day)


def force_timestamp(d):
    return int(time.mktime(d.timetuple()))


def assemble_datetime(d, t):
    """Make a datetime out of a date and a time. Ignores seconds and microseconds."""
    return datetime(d.year, d.month, d.day, t.tm_hour, minute=t.tm_min)


def flatten(list_of_lists):
    for sublist in list_of_lists:
        for item in sublist:
            yield item



if __name__ == '__main__':
    main()
