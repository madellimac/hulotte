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
    Comparator(int frame_size)
        : Stateful(), frame_size(frame_size), n_errors_total(0), n_frames(0)
    {
        this->set_name("Comparator");
        this->set_short_name("Comparator");

        auto &t    = this->create_task("check");
        auto p_ref = this->create_socket_in<int>(t, "in_ref", frame_size);
        auto p_got = this->create_socket_in<int>(t, "in_got", frame_size);

        this->create_codelet(t, [p_ref, p_got](Module &m, runtime::Task &t, const size_t /*frame_id*/) -> int {
            auto &self       = static_cast<Comparator&>(m);
            const int* ref   = static_cast<const int*>(t[p_ref].get_dataptr());
            const int* got   = static_cast<const int*>(t[p_got].get_dataptr());

            int errors = 0;
            for (int i = 0; i < self.frame_size; i++)
                if (ref[i] != got[i]) errors++;

            self.n_errors_total += errors;
            self.n_frames++;
            return runtime::status_t::SUCCESS;
        });
    }

    virtual ~Comparator() = default;

    int  get_n_errors()    const { return n_errors_total; }
    int  get_frame_count()  const { return n_frames;       }
    bool has_errors()       const { return n_errors_total > 0; }
};

} // namespace module
} // namespace spu