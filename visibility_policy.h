#ifndef Z13_VISIBILITY_POLICY_H
#define Z13_VISIBILITY_POLICY_H

#include <stdbool.h>

/* Keep the distinction between a user-requested hide and focus-loss hiding in
 * one small, testable policy.  The actual Wayland surface remains owned by
 * main.c; this policy only decides whether a later input-method batch is
 * allowed to request that surface again. */
struct z13_visibility_policy {
    bool input_method_active;
    bool manually_hidden;
    bool touch_reopen_pending;
    bool ignore_until_touch_release;
};

static inline void
z13_visibility_activate(struct z13_visibility_policy *policy)
{
    policy->input_method_active = true;
    policy->touch_reopen_pending = false;
    policy->ignore_until_touch_release = false;
}

static inline void
z13_visibility_deactivate(struct z13_visibility_policy *policy)
{
    policy->input_method_active = false;
    policy->manually_hidden = false;
    policy->touch_reopen_pending = false;
    policy->ignore_until_touch_release = false;
}

static inline void
z13_visibility_manual_hide(struct z13_visibility_policy *policy)
{
    policy->manually_hidden = true;
    policy->touch_reopen_pending = false;
    policy->ignore_until_touch_release = true;
}

static inline void
z13_visibility_automatic_hide(struct z13_visibility_policy *policy)
{
    policy->manually_hidden = false;
    policy->touch_reopen_pending = false;
    policy->ignore_until_touch_release = false;
}

static inline void
z13_visibility_shown(struct z13_visibility_policy *policy)
{
    policy->manually_hidden = false;
    policy->touch_reopen_pending = false;
    policy->ignore_until_touch_release = false;
}

static inline bool
z13_visibility_touch_event(struct z13_visibility_policy *policy, bool hidden,
                           bool pressed)
{
    if (!pressed) {
        policy->ignore_until_touch_release = false;
        return false;
    }
    if (policy->ignore_until_touch_release)
        return false;
    policy->touch_reopen_pending =
        policy->input_method_active && policy->manually_hidden && hidden;
    return policy->touch_reopen_pending;
}

static inline bool
z13_visibility_reopen_after_touch_delay(
    const struct z13_visibility_policy *policy, bool hidden)
{
    return policy->input_method_active && policy->manually_hidden &&
           policy->touch_reopen_pending && hidden;
}

static inline void
z13_visibility_cancel_touch_reopen(struct z13_visibility_policy *policy)
{
    policy->touch_reopen_pending = false;
}

#endif
