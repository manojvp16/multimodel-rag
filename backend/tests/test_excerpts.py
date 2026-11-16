from omnirag.retrieval.excerpts import readable_excerpt


def test_legacy_midword_excerpt_recovers_actual_source_characters():
    source = 'Experience\nDeveloped and maintained backend applications with Java.\nProjects'
    start = source.index('veloped')
    end = source.index('applications') + 5
    chunk = {'modality': 'text', 'content': source[start:end], 'char_start': start, 'char_end': end}
    assert readable_excerpt(chunk, {'content': source}) == 'Developed and maintained backend applications'
    assert chunk['content'].startswith('veloped')  # Indexed provenance remains unchanged.


def test_excerpt_never_invents_missing_characters():
    source = 'veloped and maintained backend'
    chunk = {'modality': 'text', 'content': source, 'char_start': 0, 'char_end': len(source)}
    assert readable_excerpt(chunk, {'content': source}) == source
    assert readable_excerpt(chunk, None) == source
    assert readable_excerpt(chunk, {'content': 'different source'}) == source


def test_caption_and_invalid_offsets_are_not_expanded():
    chunk = {'modality': 'image', 'content': 'Generated caption', 'char_start': 1, 'char_end': 8}
    assert readable_excerpt(chunk, {'content': 'Original image description'}) == 'Generated caption'
    chunk['modality'] = 'text'
    chunk['char_start'] = -1
    assert readable_excerpt(chunk, {'content': 'Generated caption'}) == 'Generated caption'
