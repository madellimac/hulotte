#pragma once
#include <streampu.hpp>

namespace spu {
namespace module {

/**
 * Comparator — StreamPU sink module for non-regression testing.
 *
 * Task  : check(in_ref[], in_got[])
 * Sinks : two input sockets (no output — terminal node like Finalizer)
 *
 * After running a sequence, check has_errors() / get_n_errors().
 * When used in generated projects, the main() returns 1 if errors > 0,
 * allowing test.sh to detect failures via exit code.
 */
class Comparator : public Stateful {
private:
    int frame_size;
    int n_errors_total;
    int n_frames;

public:
    Comparator(int frame_size);
    virtual ~Comparator();

    int  get_n_errors() const;
    int  get_frame_count() const;
    bool has_errors() const;
};

} // namespace module
} // namespace spu