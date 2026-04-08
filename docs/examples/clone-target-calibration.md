# Clone-target mic calibration

HeadMatch can use clone targets as a practical mic calibration technique for binaural measurement rigs.

The goal is not to make the microphones perfectly flat. The goal is to make measurements more comparable within a specific rig, head, and placement setup by anchoring them to a reference headphone.

## Workflow

1. **Choose a reference headphone with published measurements**
   - Pick a headphone that is well covered in the literature or in trusted measurement databases.
   - Prefer something with stable, repeatable measurements and a known tonal balance.

2. **Measure the reference headphone with your rig**
   - Use your normal binaural setup.
   - Keep the placement and sealing method consistent with how you measure other headphones.

3. **Save the measurement as a calibration target**
   - Use the measured reference response as the baseline for your clone-target workflow.
   - This becomes the target you compare other headphones against.

4. **Measure other headphones against this target**
   - Measure the next headphone on the same rig.
   - Use the reference-based clone target as the comparison target for fitting and interpretation.

## What this calibration does

This approach lets the rig's mic coloration cancel out when you compare later measurements against the same reference baseline.

In practice, it gives you a repeatable internal reference for your own setup, which is often enough to make headphone-to-headphone comparisons meaningful.

## Limitations

- Calibration is only valid for the same rig/head combination.
- Differences in seal, position, and placement still matter.
- The reference headphone should be well measured in the literature; weak or inconsistent reference data makes the calibration less trustworthy.
- This is not an automatic mic-response solver; it is a manual workflow built on clone targets.

## When to use it

Use this when you already trust your rig mechanically, but want a more grounded way to compare headphones without treating the microphone as ideally flat.

If you later change the coupler, ear simulator, placement style, or head-related setup, redo the calibration from a fresh reference measurement.
