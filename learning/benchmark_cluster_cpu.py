"""Small local, single-worker extraction benchmark for supplied frozen cases.

This module never discovers or reads snapshots. The caller supplies bytes and
reviewed Python source, checks frozen hashes, and performs quality validation
separately. Executing source here is trusted-code execution, not a sandbox.
"""
import hashlib
import math
import os
import platform
import statistics
import sys
import time

from lxml import etree


def _percentile(values, fraction):
    """Nearest-rank percentile; no interpolation on this deliberately tiny set."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _hardware():
    model = platform.processor()
    if sys.platform == 'win32':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                model = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
        except (OSError, ImportError):
            pass
    return {
        'platform': platform.platform(),
        'cpu_model': model or 'not reported',
        'logical_cpu_count': os.cpu_count(),
        'python_version': platform.python_version(),
        'lxml_version': '.'.join(map(str, etree.LXML_VERSION)),
        'libxml_version': '.'.join(map(str, etree.LIBXML_VERSION)),
    }


def benchmark(cases, repeats=7, warmups=2):
    """Measure extract(bytes) calls; compile once per cluster, outside timing.

    Each case must contain cluster_id, file, data (bytes), and source (str).
    A fixed case order is repeated, after complete-batch warmups. Per-page wall
    and process CPU durations cover the extraction call, including HTML parsing
    and result construction. Batch timing also includes measurement bookkeeping.
    Compilation, snapshot reads, validation, JSON serialization, network, model
    work, and cold worker startup are excluded. Exceptions are retained rather
    than silently removing unsuccessful attempts from the throughput denominator.
    """
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 1:
        raise ValueError('repeats must be an integer >= 1')
    if isinstance(warmups, bool) or not isinstance(warmups, int) or warmups < 0:
        raise ValueError('warmups must be an integer >= 0')
    cases = list(cases)
    if not cases:
        raise ValueError('at least one supplied case is required')
    modules = {}
    prepared = []
    for case in cases:
        cluster, filename, data, source = (case[k] for k in
                                           ('cluster_id', 'file', 'data', 'source'))
        if not isinstance(cluster, str) or not cluster or not isinstance(filename, str):
            raise ValueError('cluster_id and file must be strings; cluster_id cannot be empty')
        if not isinstance(data, bytes) or not isinstance(source, str):
            raise ValueError('data must be bytes and source must be str')
        if cluster in modules and modules[cluster]['source'] != source:
            raise ValueError('a cluster cannot use multiple candidate sources')
        if cluster not in modules:
            namespace = {'__name__': 'trusted_benchmark_candidate'}
            exec(compile(source, '<trusted-benchmark-candidate>', 'exec'), namespace)
            extractor = namespace.get('extract')
            if not callable(extractor):
                raise ValueError('candidate must define callable extract')
            modules[cluster] = {'source': source, 'extract': extractor}
        prepared.append((cluster, filename, data, modules[cluster]['extract']))

    warmup_errors = []
    for repeat in range(warmups):
        for cluster, filename, data, extractor in prepared:
            try:
                extractor(data)
            except Exception as exc:
                warmup_errors.append({'repeat': repeat + 1, 'cluster_id': cluster,
                                      'file': filename, 'error_type': type(exc).__name__,
                                      'error': str(exc)[:1000]})

    measurements, batches = [], []
    for repeat in range(repeats):
        batch_wall_start, batch_cpu_start = time.perf_counter(), time.process_time()
        batch_successes = 0
        for cluster, filename, data, extractor in prepared:
            wall_start, cpu_start = time.perf_counter(), time.process_time()
            error = None
            try:
                result = extractor(data)
            except Exception as exc:
                error = {'error_type': type(exc).__name__, 'error': str(exc)[:1000]}
            cpu_seconds = time.process_time() - cpu_start
            wall_seconds = time.perf_counter() - wall_start
            row = {'repeat': repeat + 1, 'cluster_id': cluster, 'file': filename,
                   'wall_seconds': wall_seconds, 'cpu_seconds': cpu_seconds,
                   'status': 'error' if error else 'ok'}
            if error:
                row.update(error)
            else:
                batch_successes += 1
                # Metadata only; validity and semantic quality are caller concerns.
                row['output_type'] = type(result).__name__
                result = None
            measurements.append(row)
        batch_cpu = time.process_time() - batch_cpu_start
        batch_wall = time.perf_counter() - batch_wall_start
        batches.append({'repeat': repeat + 1, 'attempts': len(prepared),
                        'successes': batch_successes, 'wall_seconds': batch_wall,
                        'cpu_seconds': batch_cpu,
                        'successful_pages_per_wall_second': batch_successes / batch_wall if batch_wall else None})

    successes = [r for r in measurements if r['status'] == 'ok']
    wall_total = sum(b['wall_seconds'] for b in batches)
    cpu_total = sum(b['cpu_seconds'] for b in batches)
    page_walls = [r['wall_seconds'] for r in successes]
    page_cpus = [r['cpu_seconds'] for r in successes]
    return {
        'method': 'single-process single-worker trusted extractor, compiled once per cluster',
        'hardware': _hardware(), 'worker_count': 1,
        'cases_per_batch': len(prepared), 'repeats': repeats, 'warmup_batches': warmups,
        'input_bytes_per_batch': sum(len(p[2]) for p in prepared),
        'measured_input_bytes': repeats * sum(len(p[2]) for p in prepared),
        'candidate_sources': [
            {'cluster_id': cluster,
             'source_utf8_sha256': hashlib.sha256(module['source'].encode('utf-8')).hexdigest()}
            for cluster, module in modules.items()],
        'warmup_errors': warmup_errors, 'batches': batches, 'measurements': measurements,
        'summary': {
            'attempts': len(measurements), 'successes': len(successes),
            'failures': len(measurements) - len(successes),
            'execution_failure_rate': (len(measurements) - len(successes)) / len(measurements),
            'batch_wall_seconds_total': wall_total, 'batch_cpu_seconds_total': cpu_total,
            'batch_wall_seconds_median': statistics.median(b['wall_seconds'] for b in batches),
            'successful_pages_per_wall_second': len(successes) / wall_total if wall_total else None,
            'successful_pages_per_cpu_second': len(successes) / cpu_total if cpu_total else None,
            'successful_page_wall_seconds_p50': _percentile(page_walls, .5),
            'successful_page_wall_seconds_p95': _percentile(page_walls, .95),
            'successful_page_cpu_seconds_mean': statistics.mean(page_cpus) if page_cpus else None,
            'successful_page_cpu_seconds_p50': _percentile(page_cpus, .5),
            'successful_page_cpu_seconds_p95': _percentile(page_cpus, .95),
        },
        'limits': [
            'Extraction-call timing excludes file reads, compile/import, validation, serialization, network, model generation/repair/review and cold process startup.',
            'Fixed case order, warm in-memory input and one worker; repeated pages are not independent quality samples.',
            'Execution success is not contract validity or semantic accuracy. Quality must be evaluated separately.',
            'CPU process time includes this process only. Small local measurements cannot establish distributed or trillion-page throughput.',
            'No per-page GPU/model baseline is measured; this is not an empirical GPU cost-reduction comparison.',
        ],
    }


def cost_scenario(n, generation_repair_cost, cpu_seconds_per_page,
                  cpu_price_per_hour, audit_total_cost):
    """Assumed monetary cost, same caller-chosen currency across all inputs.

    CPU price is per CPU-process-hour, not wall-clock machine/GPU-hour. This
    formula does not infer API token costs or price unrecorded conversation work.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError('n must be a positive integer')
    values = {'generation_repair_cost': generation_repair_cost,
              'cpu_seconds_per_page': cpu_seconds_per_page,
              'cpu_price_per_hour': cpu_price_per_hour,
              'audit_total_cost': audit_total_cost}
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(name + ' must be finite and nonnegative')
    cpu_per_page = cpu_seconds_per_page * cpu_price_per_hour / 3600
    total = generation_repair_cost + n * cpu_per_page + audit_total_cost
    return {'pages': n, **values, 'cpu_cost_per_page': cpu_per_page,
            'total_cost': total, 'amortized_cost_per_page': total / n,
            'formula': '(generation_repair_cost + n * cpu_cost_per_page + audit_total_cost) / n',
            'status': 'assumption-based scenario, not observed billing or measured GPU savings'}
