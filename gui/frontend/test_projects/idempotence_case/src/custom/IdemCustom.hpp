#pragma once
#include <streampu.hpp>

namespace spu {
namespace module {

class IdemCustom : public Stateful
{
private:
    int n_elmts;

public:
    IdemCustom(const int n_elmts);
    virtual ~IdemCustom() = default;
    
    virtual IdemCustom* clone() const override;

protected:
    void _process(const int* in, int* out, const int frame_id);
};

}
}