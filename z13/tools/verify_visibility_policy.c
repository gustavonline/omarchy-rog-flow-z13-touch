#include <assert.h>
#include <stdbool.h>

#include "visibility_policy.h"

int
main(void)
{
    struct z13_visibility_policy policy = {0};

    /* A normal activation does not arm a hidden-surface touch reopen. */
    z13_visibility_activate(&policy);
    assert(!z13_visibility_touch_event(&policy, false, true));

    /* The touch which pressed Hide is ignored through its release.  A later
     * touch may reopen after the compositor gets time to report focus loss. */
    z13_visibility_manual_hide(&policy);
    assert(!z13_visibility_touch_event(&policy, true, true));
    assert(!z13_visibility_touch_event(&policy, true, false));
    assert(z13_visibility_touch_event(&policy, true, true));
    assert(z13_visibility_reopen_after_touch_delay(&policy, true));
    z13_visibility_shown(&policy);
    assert(!z13_visibility_reopen_after_touch_delay(&policy, true));

    /* Focus loss during the delay cancels the pending reopen. */
    z13_visibility_manual_hide(&policy);
    assert(!z13_visibility_touch_event(&policy, true, false));
    assert(z13_visibility_touch_event(&policy, true, true));
    z13_visibility_deactivate(&policy);
    assert(!z13_visibility_reopen_after_touch_delay(&policy, true));

    /* Automatic focus-loss hiding never arms the manual touch path. */
    z13_visibility_activate(&policy);
    z13_visibility_automatic_hide(&policy);
    assert(!z13_visibility_touch_event(&policy, true, true));

    /* Explicit cancellation is idempotent and suppresses a scheduled show. */
    z13_visibility_manual_hide(&policy);
    assert(!z13_visibility_touch_event(&policy, true, false));
    assert(z13_visibility_touch_event(&policy, true, true));
    z13_visibility_cancel_touch_reopen(&policy);
    assert(!z13_visibility_reopen_after_touch_delay(&policy, true));

    return 0;
}
