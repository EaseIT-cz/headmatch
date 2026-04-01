from headmatch.contracts import ConfidenceSummary
from headmatch.troubleshooting import confidence_troubleshooting_steps


def test_troubleshooting_steps_follow_existing_warnings():
    confidence = ConfidenceSummary(
        score=42,
        label='low',
        headline='This run looks suspicious.',
        interpretation='The run may not be trustworthy.',
        reasons=(),
        warnings=(
            'Alignment to the sweep was weaker than expected, so the measurement timing may be unreliable.',
            'Left and right measurements differ more than usual, which often means the headset or microphones were not seated consistently.',
            'The fitted result still leaves noticeable residual error, so the generated EQ should be treated as provisional.',
        ),
        metrics={},
    )

    steps = confidence_troubleshooting_steps(confidence)

    assert steps[0] == 'Try one fresh rerun before keeping this EQ preset.'
    assert any('start the sweep again' in step for step in steps)
    assert any('Re-seat the headphones and microphones carefully' in step for step in steps)
