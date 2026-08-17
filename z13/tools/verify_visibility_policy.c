#include <assert.h>
#include <stdbool.h>

#include "visibility_policy.h"

int
main(void)
{
    struct z13_visibility_policy policy = {0};

    /* A normal activation shows once and an ordinary done batch is inert. */
    z13_visibility_activate(&policy);
    assert(!z13_visibility_reopen_from_done(&policy, false));

    /* Hide-key followed by the next generation may reopen the same field. */
    z13_visibility_manual_hide(&policy);
    assert(z13_visibility_reopen_from_done(&policy, true));
    assert(z13_visibility_reopen_from_surrounding_text(&policy, true));
    z13_visibility_shown(&policy);
    assert(!z13_visibility_reopen_from_done(&policy, true));

    /* Focus loss must clear manual state and never reopen from stale done. */
    z13_visibility_manual_hide(&policy);
    z13_visibility_deactivate(&policy);
    assert(!z13_visibility_reopen_from_done(&policy, true));
    assert(!z13_visibility_reopen_from_surrounding_text(&policy, true));

    /* Automatic hiding strips the done-only manual-reopen privilege.  An
     * explicit surrounding-text refresh remains a valid active-field event. */
    z13_visibility_activate(&policy);
    z13_visibility_automatic_hide(&policy);
    assert(!z13_visibility_reopen_from_done(&policy, true));
    assert(z13_visibility_reopen_from_surrounding_text(&policy, true));

    return 0;
}
