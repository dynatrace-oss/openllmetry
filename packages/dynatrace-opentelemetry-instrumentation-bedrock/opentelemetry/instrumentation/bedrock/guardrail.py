from opentelemetry.semconv_ai import SpanAttributes
from enum import Enum

class Type(Enum):
    INPUT = 'input'
    OUTPUT = 'output'


def is_guardrail_activated(response):
    if 'results' in response:
        for message in response['results']:
            if message.get('completionReason') == 'CONTENT_FILTERED':
                return True
    if response.get('stopReason') == 'guardrail_intervened':
        return True
    return response.get('amazon-bedrock-guardrailAction') != "NONE"

def handle_invoke_metrics(t: Type, guardrail, attrs, metric_params):
    if 'invocationMetrics' in guardrail:
        if 'guardrailProcessingLatency' in guardrail['invocationMetrics']:
            input_latency = guardrail['invocationMetrics']['guardrailProcessingLatency']
            metric_params.guardrail_latency_histogram.record(input_latency, attributes={
                **attrs,
                SpanAttributes.LLM_TOKEN_TYPE: t.value,
            })
        if 'guardrailCoverage' in guardrail['invocationMetrics']:
            coverage = guardrail['invocationMetrics']['guardrailCoverage']
            char_guarded = coverage['textCharacters']['guarded']
            metric_params.guardrail_coverage.add(char_guarded, attributes={
                **attrs,
                SpanAttributes.LLM_TOKEN_TYPE: t.value,
            })

def handle_sensitive(t: Type, guardrail, attrs, metric_params):
    if 'sensitiveInformationPolicy' in guardrail:
        sensitive_info = guardrail['sensitiveInformationPolicy']
        if 'piiEntities' in sensitive_info:
            for entry in sensitive_info['piiEntities']:
                metric_params.guardrail_sensitive_info.add(1, attributes = {
                    **attrs,
                    "gen_ai.guardrail.type": t.value,
                    "gen_ai.guardrail.pii": entry['type'],
                })
        if 'regexes' in sensitive_info:
            for entry in sensitive_info['regexes']:
                metric_params.guardrail_sensitive_info.add(1, attributes = {
                    **attrs,
                    "gen_ai.guardrail.type": t.value,
                    "gen_ai.guardrail.pattern": entry['name'],
                })

def handle_topic(t: Type, guardrail, attrs, metric_params):
    if 'topicPolicy' in guardrail:
        topics = guardrail['topicPolicy']['topics']
        for topic in topics:
            metric_params.guardrail_topic.add(1, attributes = {
                **attrs,
                "gen_ai.guardrail.type": t.value,
                "gen_ai.guardrail.topic": topic['name'],
            })

def handle_content(t: Type, guardrail, attrs, metric_params):
    if 'contentPolicy' in guardrail:
        filters = guardrail['contentPolicy']['filters']
        for filter in filters:
            metric_params.guardrail_content.add(1, attributes = {
                **attrs,
                "gen_ai.guardrail.type": t.value,
                "gen_ai.guardrail.content": filter['type'],
                "gen_ai.guardrail.confidence": filter['confidence'],
            })

def handle_words(t: Type, guardrail, attrs, metric_params):
    if 'wordPolicy' in guardrail:
        filters = guardrail['wordPolicy']
        if 'customWords' in filters:
            for filter in filters['customWords']:
                metric_params.guardrail_words.add(1, attributes = {
                    **attrs,
                    "gen_ai.guardrail.type": t.value,
                    "gen_ai.guardrail.match": filter['match'],
                })
        if 'managedWordLists' in filters:
            for filter in filters['managedWordLists']:
                metric_params.guardrail_words.add(1, attributes = {
                    **attrs,
                    "gen_ai.guardrail.type": t.value,
                    "gen_ai.guardrail.match": filter['match'],
                })

def guardrail_converse(response, vendor, model, metric_params):
    attrs = {
        "gen_ai.vendor": vendor,
        SpanAttributes.LLM_RESPONSE_MODEL: model,
        SpanAttributes.LLM_SYSTEM: "bedrock",
    }
    if 'trace' in response and 'guardrail' in response['trace']:
        g = response['trace']['guardrail']
        if 'inputAssessment' in g:
            g_id = next(iter(g['inputAssessment']))
            attrs["gen_ai.guardrail"] = g_id
            guardrail_info = g['inputAssessment'][g_id]
            _handle(Type.INPUT, guardrail_info, attrs, metric_params)
        if 'outputAssessments' in g:
            g_id = next(iter(g['outputAssessments']))
            attrs["gen_ai.guardrail"] = g_id
            guardrail_infos = g['outputAssessments'][g_id]
            for guardrail_info in guardrail_infos:
                _handle(Type.OUTPUT, guardrail_info, attrs, metric_params)
    if is_guardrail_activated(response):
        metric_params.guardrail_counter.add(1, attrs)

def guardrail_handling(response_body, vendor, model, metric_params):
    if 'amazon-bedrock-guardrailAction' in response_body:
        attrs = {
            "gen_ai.vendor": vendor,
            SpanAttributes.LLM_RESPONSE_MODEL: model,
            SpanAttributes.LLM_SYSTEM: "bedrock",
        }
        if 'amazon-bedrock-trace' in response_body:
            bedrock_trace = response_body['amazon-bedrock-trace']
            if 'guardrail' in bedrock_trace and 'input' in bedrock_trace['guardrail']:
                g_id = next(iter(bedrock_trace['guardrail']['input']))
                attrs["gen_ai.guardrail"] = g_id
                guardrail_info = bedrock_trace['guardrail']['input'][g_id]
                _handle(Type.INPUT, guardrail_info, attrs, metric_params)

            if 'guardrail' in bedrock_trace and 'outputs' in bedrock_trace['guardrail']:
                outputs = bedrock_trace['guardrail']['outputs']
                for output in outputs:
                    g_id = next(iter(output))
                    attrs["gen_ai.guardrail"] = g_id
                    guardrail_info = outputs[0][g_id]
                    _handle(Type.OUTPUT, guardrail_info, attrs, metric_params)

        if is_guardrail_activated(response_body):
            metric_params.guardrail_counter.add(1, attrs)

def _handle(t: Type, guardrail_info, attrs, metric_params):
    handle_invoke_metrics(t, guardrail_info, attrs, metric_params)
    handle_sensitive(t, guardrail_info, attrs, metric_params)
    handle_topic(t, guardrail_info, attrs, metric_params)
    handle_content(t, guardrail_info, attrs, metric_params)
    handle_words(t, guardrail_info, attrs, metric_params)