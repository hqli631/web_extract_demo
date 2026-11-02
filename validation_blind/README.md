# Frozen validation batch

This directory is isolated from the development samples. Do not change extraction rules based on this batch until the review record is complete.

The batch uses two URLs supplied earlier in the project conversation: one Toutiao article and one Sina K article. Collection is limited to one page per exact host. The Sina K request could not be collected because the HTTPS connection failed before robots.txt could be checked. The collector conservatively skipped it; this does not prove the site explicitly disallowed access.

## Reproduce

1. Set PYTHONPATH to .deps and run run_blind_validation.py --collect. The static Toutiao response may contain no article text.
2. For the allowlisted Toutiao target, set NODE_PATH to the bundled Node modules and run capture_dynamic_validation.cjs toutiao. This saves a rendered DOM snapshot here without adding it to the main samples directory.
3. Run run_blind_validation.py to regenerate the extraction report.
4. Compare the extraction against the rendered article and record decisions in reports/ai_review.json. Each decision must be bound to the file name and snapshot SHA-256.
5. Do not modify the extractor until the frozen audit is complete. After changes, pass a new --batch path to run_blind_validation.py and as the third argument to capture_dynamic_validation.cjs rather than reusing this batch as evidence for the changed code.

## Current review

The saved Toutiao article contains three narrative paragraphs. The title and publication metadata are separate; editor attribution, controls, comments, and recommendation cards are excluded. The current frozen extractor matches all three paragraphs in order. This is one AI-reviewed development check, not human ground truth or a cross-site accuracy estimate.

The Sina K URL was not fetched because robots.txt could not be retrieved over HTTPS. Do not bypass this failure; retry later or use a different permitted source.
