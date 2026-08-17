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
};

static inline void
z13_visibility_activate(struct z13_visibility_policy *policy)
{
    policy->input_method_active = true;
}

static inline void
z13_visibility_deactivate(struct z13_visibility_policy *policy)
{
    policy->input_method_active = false;
    policy->manually_hidden = false;
}

static inline void
z13_visibility_manual_hide(struct z13_visibility_policy *policy)
{
    policy->manually_hidden = true;
}

static inline void
z13_visibility_automatic_hide(struct z13_visibility_policy *policy)
{
    policy->manually_hidden = false;
}

static inline void
z13_visibility_shown(struct z13_visibility_policy *policy)
{
    policy->manually_hidden = false;
}

static inline bool
z13_visibility_reopen_from_surrounding_text(
    const struct z13_visibility_policy *policy, bool hidden)
{
    return policy->input_method_active && hidden;
}

static inline bool
z13_visibility_reopen_from_done(
    const struct z13_visibility_policy *policy, bool hidden)
{
    return policy->input_method_active && hidden && policy->manually_hidden;
}

#endif
